# echo: file_searcher ingest_file_to_development v0.1.0 2025-11-24

"""
Ingest a single text file into the "development" environment.

Flow (development env only):
  1) raw.documents_development: insert or reuse existing doc row (idempotent on source_path + file_name)
  2) stg.document_text_development: upsert cleaned text for that doc_id
  3) int.chunks_development: delete existing chunks for doc_id, insert fresh chunks from chunker

Sections:
  1) Imports & constants
  2) DB helpers (wrap init_db)
  3) Ingestion helpers (raw / stg / int)
  4) CLI / main entrypoint
"""

# =====================================================
# 1) Imports & constants
# =====================================================

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import psycopg2
from psycopg2.extras import register_uuid

from .chunker import split_text_into_chunks, TextChunk
from .init_db import load_config, get_conn
from .extract_text import extract_text_from_file



# =====================================================
# 2) DB helpers (wrap init_db)
# =====================================================

def get_connection():
    """
    Get a psycopg2 connection using the same config logic as init_db.
    """
    config = load_config()
    conn = get_conn(config)
    # Make sure UUID types are handled nicely
    register_uuid()
    return conn


# =====================================================
# 3) Ingestion helpers
# =====================================================

def get_or_create_document_development(
    cur,
    *,
    file_path: Path,
    mime_type: str | None,
    payload_raw: bytes | None,
) -> str:
    """
    Idempotent insert for raw.documents_development.

    Logic:
      - Look up by (source_path, file_name).
      - If exists, return existing doc_id.
      - If not, insert and return new doc_id.
    """
    source_path = str(file_path.resolve())
    file_name = file_path.name

    # 3.1 Try to find existing row
    cur.execute(
        """
        SELECT doc_id
        FROM raw.documents_development
        WHERE source_path = %s
          AND file_name = %s
        ORDER BY collected_at DESC
        LIMIT 1;
        """,
        (source_path, file_name),
    )
    row = cur.fetchone()
    if row:
        (doc_id,) = row
        return str(doc_id)

    # 3.2 Insert new row
    cur.execute(
        """
        INSERT INTO raw.documents_development (
            source_path,
            file_name,
            mime_type,
            payload_raw
        )
        VALUES (%s, %s, %s, %s)
        RETURNING doc_id;
        """,
        (source_path, file_name, mime_type, payload_raw),
    )
    (doc_id,) = cur.fetchone()
    return str(doc_id)


def upsert_document_text_development(
    cur,
    *,
    doc_id: str,
    text_content: str,
) -> None:
    """
    Upsert into stg.document_text_development.

    Idempotent on doc_id (PRIMARY KEY):
      - INSERT ... ON CONFLICT (doc_id) DO UPDATE
    """
    cur.execute(
        """
        INSERT INTO stg.document_text_development (
            doc_id,
            text_content,
            normalized_text
        )
        VALUES (%s, %s, %s)
        ON CONFLICT (doc_id)
        DO UPDATE SET
            text_content = EXCLUDED.text_content,
            normalized_text = EXCLUDED.normalized_text;
        """,
        (doc_id, text_content, text_content),
    )


def replace_chunks_development(
    cur,
    *,
    doc_id: str,
    chunks: List[TextChunk],
) -> None:
    """
    Idempotent replacement of chunks for a given doc_id in int.chunks_development.

    Strategy:
      - DELETE existing rows for doc_id
      - INSERT fresh rows for each chunk
    """
    # 3.3.1 Delete existing chunks for this doc_id
    cur.execute(
        """
        DELETE FROM int.chunks_development
        WHERE doc_id = %s;
        """,
        (doc_id,),
    )

    # 3.3.2 Insert new chunks
    for ch in chunks:
        meta = ch.metadata
        cur.execute(
            """
            INSERT INTO int.chunks_development (
                doc_id,
                chunk_index,
                content,
                start_char,
                end_char
            )
            VALUES (%s, %s, %s, %s, %s);
            """,
            (
                doc_id,
                meta.chunk_index,
                ch.content,
                meta.start_char,
                meta.end_char,
            ),
        )


def ingest_file_to_development(
    file_path: Path,
    *,
    mime_type: str | None = None,
    max_words: int = 220,
    overlap_words: int = 40,
) -> None:
    """
    High-level ingestion for a single file into the development environment.

    Steps:
      1) Read file from disk (bytes + text)
      2) Chunk text with split_text_into_chunks
      3) Write to raw/stg/int development tables in a single transaction
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    # 1) Read file
    payload_raw = file_path.read_bytes()
    # Extract human-readable text (txt/pdf-aware)
    text = extract_text_from_file(file_path, mime_type=mime_type)

    # 2) Chunk the text
    chunks = split_text_into_chunks(
        text,
        max_words=max_words,
        overlap_words=overlap_words,
        source_id=str(file_path),
    )

    # 3) Write to DB
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                doc_id = get_or_create_document_development(
                    cur,
                    file_path=file_path,
                    mime_type=mime_type,
                    payload_raw=payload_raw,
                )

                upsert_document_text_development(
                    cur,
                    doc_id=doc_id,
                    text_content=text,
                )

                replace_chunks_development(
                    cur,
                    doc_id=doc_id,
                    chunks=chunks,
                )
        print(f"Ingested file into development: {file_path} (doc_id={doc_id})")
        print(f"Chunks written: {len(chunks)}")
    finally:
        conn.close()


# =====================================================
# 4) CLI / main entrypoint
# =====================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a text file into the file_searcher development environment."
    )
    parser.add_argument(
        "path",
        type=str,
        help="Path to a text file to ingest.",
    )
    parser.add_argument(
        "--mime-type",
        type=str,
        default="text/plain",
        help="Optional MIME type (default: text/plain).",
    )
    parser.add_argument(
        "--max-words",
        type=int,
        default=220,
        help="Maximum words per chunk.",
    )
    parser.add_argument(
        "--overlap-words",
        type=int,
        default=40,
        help="Word overlap between chunks.",
    )

    args = parser.parse_args()
    file_path = Path(args.path)

    ingest_file_to_development(
        file_path=file_path,
        mime_type=args.mime_type,
        max_words=args.max_words,
        overlap_words=args.overlap_words,
    )


if __name__ == "__main__":
    main()
