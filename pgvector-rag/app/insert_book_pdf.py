"""
insert_book_pdf.py
Version: v0.3.0 (2025-11-17)

Pipeline:
- Read a single PDF (Fundamentals of Data Engineering)
- Insert raw text into bronze.web_docs (append-only, idempotent on (source_name, payload_hash))
- Chunk text and insert embeddings into vector.doc_chunks using pgvector + Ollama embeddings
"""

import os
import uuid
import hashlib
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
import psycopg2
from psycopg2.extras import Json

SCRIPT_VERSION = "v0.3.0 (2025-11-17)"


def load_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.strip()
        if not text:
            continue
        pages.append(f"[Page {i + 1}]\n{text}")
    return "\n\n".join(pages)


def chunk_text(text: str, max_chars: int = 1200) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for p in paragraphs:
        if not current:
            if len(p) <= max_chars:
                current = p
            else:
                for i in range(0, len(p), max_chars):
                    chunks.append(p[i : i + max_chars])
                current = ""
        else:
            candidate = current + "\n\n" + p
            if len(candidate) <= max_chars:
                current = candidate
            else:
                chunks.append(current)
                if len(p) <= max_chars:
                    current = p
                else:
                    for i in range(0, len(p), max_chars):
                        chunks.append(p[i : i + max_chars])
                    current = ""

    if current:
        chunks.append(current)

    return chunks


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5433"),
        dbname=os.getenv("PGDATABASE", "chat_ingest"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
    )


def main():
    print(f"[insert_book_pdf] Starting (version {SCRIPT_VERSION})")

    load_dotenv()

    # Use Ollama via OpenAI-compatible API
    client = OpenAI(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
    )

    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    pdf_path = os.getenv(
        "BOOK_PDF_PATH",
        r"E:\pgvectorscale-rag\Library\Fundamentals of Data Engineering (Reis, JoeHousley, Matt) (Z-Library).pdf",
    )
    source_name = os.getenv("BOOK_SOURCE_NAME", "Fundamentals of Data Engineering")
    contract_name = os.getenv("BOOK_CONTRACT_NAME", "fde_book")
    contract_ver = os.getenv("BOOK_CONTRACT_VER", "v1")

    print(f"[insert_book_pdf] Reading PDF from: {pdf_path}")
    full_text = load_pdf_text(pdf_path)
    if not full_text:
        raise RuntimeError("No text extracted from PDF – check file or extractor.")

    payload_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
    print(f"[insert_book_pdf] Extracted {len(full_text)} characters; hash={payload_hash[:12]}...")

    conn = get_pg_connection()
    conn.autocommit = False

    with conn:
        with conn.cursor() as cur:
            # 1) Upsert into bronze.web_docs
            doc_id_new = str(uuid.uuid4())
            print(f"[insert_book_pdf] Upserting bronze.web_docs row (candidate doc_id={doc_id_new})")

            cur.execute(
                """
                INSERT INTO bronze.web_docs
                    (doc_id,       source_name, source_uri, payload_raw,
                     payload_hash, contract_name, contract_ver)
                VALUES
                    (%s::uuid, %s,          %s,         %s,
                     %s,        %s,            %s)
                ON CONFLICT (source_name, payload_hash)
                DO UPDATE SET
                    payload_raw   = EXCLUDED.payload_raw,
                    contract_name = EXCLUDED.contract_name,
                    contract_ver  = EXCLUDED.contract_ver
                RETURNING doc_id;
                """,
                (
                    doc_id_new,
                    source_name,
                    pdf_path,
                    full_text,
                    payload_hash,
                    contract_name,
                    contract_ver,
                ),
            )

            (doc_id,) = cur.fetchone()
            doc_id = str(doc_id)
            print(f"[insert_book_pdf] Using doc_id = {doc_id}")

            # 2) Chunk text and insert into vector.doc_chunks
            chunks = chunk_text(full_text, max_chars=1200)
            print(f"[insert_book_pdf] Generated {len(chunks)} chunks")

            for idx, chunk in enumerate(chunks):
                emb_resp = client.embeddings.create(
                    model=embed_model,
                    input=chunk,
                )
                embedding = emb_resp.data[0].embedding  # e.g. 768-dim for nomic-embed-text

                vector_literal = "[" + ",".join(f"{x:.6f}" for x in embedding) + "]"

                metadata = {
                    "source_name": source_name,
                    "source_uri": pdf_path,
                    "chunk_idx": idx,
                    "chunk_chars": len(chunk),
                    "contract_name": contract_name,
                    "contract_ver": contract_ver,
                    "ingested_at": datetime.utcnow().isoformat(),
                }

                cur.execute(
                    """
                    INSERT INTO vector.doc_chunks
                        (chunk_id,       doc_id,      chunk_idx, content, embedding, metadata)
                    VALUES
                        (%s::uuid, %s::uuid, %s,      %s,      %s::vector, %s)
                    ON CONFLICT (doc_id, chunk_idx)
                    DO UPDATE SET
                        content   = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata  = EXCLUDED.metadata;
                    """,
                    (str(uuid.uuid4()), doc_id, idx, chunk, vector_literal, Json(metadata)),
                )

                if (idx + 1) % 20 == 0:
                    print(f"[insert_book_pdf] Upserted {idx + 1}/{len(chunks)} chunks...")

    conn.close()
    print("[insert_book_pdf] Done – bronze + vector layers updated.")


if __name__ == "__main__":
    main()
