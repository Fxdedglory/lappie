# echo: file_searcher embed_development_chunks v0.1.0 2025-11-24

"""
Embed chunks for a document in the development environment using Ollama.

Flow:
  1) Resolve doc_id from file path (raw.documents_development)
  2) Load chunks from int.chunks_development for that doc_id
  3) Call Ollama embeddings in batch
  4) Replace rows in int.chunk_embeddings_development for that doc_id (idempotent)

Sections:
  1) Imports & helpers
  2) DB helpers
  3) Embedding pipeline
  4) CLI / main
"""

# =====================================================
# 1) Imports & helpers
# =====================================================

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import psycopg2
from psycopg2.extras import register_uuid

from .init_db import load_config, get_conn
from .embeddings import embed_texts


# =====================================================
# 2) DB helpers
# =====================================================

def get_connection():
    """
    Get a psycopg2 connection using the same config logic as init_db.
    """
    config = load_config()
    conn = get_conn(config)
    register_uuid()
    return conn


def resolve_doc_id_for_path(cur, file_path: Path) -> str:
    """
    Look up doc_id in raw.documents_development by source_path + file_name.

    Raises:
        RuntimeError if no matching doc is found.
    """
    source_path = str(file_path.resolve())
    file_name = file_path.name

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
    if not row:
        raise RuntimeError(
            f"No document found in raw.documents_development for path={source_path}"
        )
    (doc_id,) = row
    return str(doc_id)


def load_chunks_for_doc(cur, doc_id: str) -> List[Tuple[str, str]]:
    """
    Load (chunk_id, content) for a given doc_id from int.chunks_development.

    Returns:
        List of (chunk_id, content), ordered by chunk_index.
    """
    cur.execute(
        """
        SELECT chunk_id, content
        FROM int.chunks_development
        WHERE doc_id = %s
        ORDER BY chunk_index ASC;
        """,
        (doc_id,),
    )
    rows = cur.fetchall()
    return [(str(r[0]), r[1]) for r in rows]


def delete_embeddings_for_doc(cur, doc_id: str) -> None:
    """
    Delete existing embeddings for all chunks of this doc_id in development.

    Strategy:
      - Find chunk_ids for doc_id
      - DELETE FROM int.chunk_embeddings_development WHERE chunk_id IN (...)
    """
    cur.execute(
        """
        DELETE FROM int.chunk_embeddings_development
        WHERE chunk_id IN (
            SELECT chunk_id
            FROM int.chunks_development
            WHERE doc_id = %s
        );
        """,
        (doc_id,),
    )


def insert_embeddings_for_doc(
    cur,
    doc_id: str,
    chunk_ids: List[str],
    embeddings: List[List[float]],
) -> None:
    """
    Insert embeddings into int.chunk_embeddings_development.

    Assumes existing rows for these chunk_ids (if any) have been deleted.

    Args:
        cur: psycopg2 cursor
        doc_id: doc identifier (not used directly here, but included for clarity)
        chunk_ids: list of chunk_id strings
        embeddings: list of embedding vectors (same order as chunk_ids)
    """
    for chunk_id, emb in zip(chunk_ids, embeddings):
        cur.execute(
            """
            INSERT INTO int.chunk_embeddings_development (
                chunk_id,
                embedding
            )
            VALUES (%s, %s);
            """,
            (chunk_id, emb),
        )


# =====================================================
# 3) Embedding pipeline
# =====================================================

def embed_chunks_for_file(file_path: Path) -> None:
    """
    High-level embedding pipeline for a single file in development env.

    Steps:
      1) Resolve doc_id from raw.documents_development
      2) Load chunks from int.chunks_development
      3) Call Ollama embeddings
      4) Replace rows in int.chunk_embeddings_development for this doc_id
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                doc_id = resolve_doc_id_for_path(cur, file_path)
                rows = load_chunks_for_doc(cur, doc_id)

                if not rows:
                    raise RuntimeError(
                        f"No chunks found in int.chunks_development for doc_id={doc_id}"
                    )

                chunk_ids = [r[0] for r in rows]
                contents = [r[1] for r in rows]

                # Call Ollama for embeddings
                embeddings = embed_texts(contents)

                if len(embeddings) != len(chunk_ids):
                    raise RuntimeError(
                        f"Embedding count mismatch: "
                        f"{len(embeddings)} embeddings for {len(chunk_ids)} chunks"
                    )

                # Replace existing embeddings for this doc_id
                delete_embeddings_for_doc(cur, doc_id)
                insert_embeddings_for_doc(cur, doc_id, chunk_ids, embeddings)

        print(f"Embedded {len(chunk_ids)} chunks for file: {file_path}")
    finally:
        conn.close()


# =====================================================
# 4) CLI / main
# =====================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Embed chunks for a file in the development environment."
    )
    parser.add_argument(
        "path",
        type=str,
        help="Path to the file that has already been ingested to development.",
    )

    args = parser.parse_args()
    file_path = Path(args.path)

    embed_chunks_for_file(file_path)


if __name__ == "__main__":
    main()
