"""
search_book_faq.py
Version: v0.3.0 (2025-11-17)

- Finds the latest bronze.web_docs row for the book (by source_name)
- Interactive chat:
    * You type a question
    * It embeds the question (Ollama embeddings)
    * Runs pgvector similarity search over vector.doc_chunks for that doc_id
    * Uses an LLM (Ollama chat model) to synthesize an answer from the top-k chunks
"""

import os
from typing import List, Tuple

from dotenv import load_dotenv
from openai import OpenAI
import psycopg2

SCRIPT_VERSION = "v0.3.0 (2025-11-17)"


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5433"),
        dbname=os.getenv("PGDATABASE", "chat_ingest"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
    )


def get_latest_doc_id(conn, source_name: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT doc_id
            FROM bronze.web_docs
            WHERE source_name = %s
            ORDER BY collected_at DESC, doc_id DESC
            LIMIT 1;
            """,
            (source_name,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"No bronze.web_docs row found for source_name={source_name!r}")
        return str(row[0])


def embed_question(client: OpenAI, model: str, question: str) -> str:
    resp = client.embeddings.create(
        model=model,
        input=question,
    )
    emb = resp.data[0].embedding
    return "[" + ",".join(f"{x:.6f}" for x in emb) + "]"


def search_chunks(
    conn,
    doc_id: str,
    query_vector_literal: str,
    top_k: int = 5,
) -> List[Tuple[str, dict, float]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                content,
                metadata,
                1 - (embedding <=> %s::vector) AS score
            FROM vector.doc_chunks
            WHERE doc_id = %s::uuid
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (query_vector_literal, doc_id, query_vector_literal, top_k),
        )
        rows = cur.fetchall()

    results: List[Tuple[str, dict, float]] = []
    for content, metadata, score in rows:
        results.append((content, metadata, float(score)))
    return results


def synthesize_answer(
    client: OpenAI,
    chat_model: str,
    question: str,
    chunks: List[Tuple[str, dict, float]],
) -> str:
    if not chunks:
        return "I couldn't find any relevant content in the book for that question."

    context_blocks = []
    for i, (content, metadata, score) in enumerate(chunks, start=1):
        meta_str = f"chunk_idx={metadata.get('chunk_idx')}, score={score:.3f}"
        context_blocks.append(f"[Chunk {i} | {meta_str}]\n{content}")

    context_text = "\n\n".join(context_blocks)

    completion = client.chat.completions.create(
        model=chat_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that answers questions ONLY "
                    "about the book 'Fundamentals of Data Engineering'. "
                    "Base your answers strictly on the provided context; if the "
                    "answer is not in the context, say you don't know."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Context from the book (multiple chunks):\n\n{context_text}"
                ),
            },
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content.strip()


def main():
    print(f"[search_book_faq] Starting (version {SCRIPT_VERSION})")

    load_dotenv()

    # Ollama via OpenAI-compatible API
    client = OpenAI(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
    )

    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    chat_model = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
    source_name = os.getenv("BOOK_SOURCE_NAME", "Fundamentals of Data Engineering")

    conn = get_pg_connection()

    try:
        doc_id = get_latest_doc_id(conn, source_name)
        print(f"[search_book_faq] Using doc_id = {doc_id} for source_name={source_name!r}")
        print("Type questions about the book. Enter '/q' or blank line to exit.\n")

        while True:
            try:
                q = input("Q> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[search_book_faq] Exiting.")
                break

            if not q or q.lower() in {"/q", "quit", "exit"}:
                print("[search_book_faq] Bye.")
                break

            q_vec = embed_question(client, embed_model, q)
            chunks = search_chunks(conn, doc_id, q_vec, top_k=5)
            answer = synthesize_answer(client, chat_model, q, chunks)

            print("\n--- Answer ---\n")
            print(answer)
            print("\n--------------\n")

    finally:
        conn.close()
        print("[search_book_faq] Done.")


if __name__ == "__main__":
    main()
