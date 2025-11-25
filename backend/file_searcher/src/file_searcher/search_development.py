# echo: file_searcher search_development v0.1.0 2025-11-24

"""
Search over development environment using pgvector + Ollama embeddings.

Flow:
  1) Embed the query with Ollama
  2) Query int.chunk_embeddings_development by vector similarity
  3) Join back to chunks + documents for metadata
  4) Print top-k results with previews

Sections:
  1) Imports & helpers
  2) DB search
  3) CLI / main
"""

# =====================================================
# 1) Imports & helpers
# =====================================================

from __future__ import annotations

import argparse
from typing import List, Tuple

import psycopg2
from psycopg2.extras import register_uuid

from .init_db import load_config, get_conn
from .embeddings import embed_text


def get_connection():
    """
    Get a psycopg2 connection using the same config logic as init_db.
    """
    config = load_config()
    conn = get_conn(config)
    register_uuid()
    return conn


def _vector_to_pg_literal(vec: List[float]) -> str:
    """
    Convert a Python list[float] into a pgvector literal string: '[v1,v2,...]'.

    We'll parametrize this as %s::vector in SQL to avoid manual casting.
    """
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


# =====================================================
# 2) DB search
# =====================================================

def search_development(
    query: str,
    *,
    top_k: int = 5,
) -> List[Tuple]:
    """
    Perform a semantic search in the development environment.

    Returns:
        List of rows, each row containing:
          (rank, score, file_name, chunk_index, content_preview)
    """
    # 1) Embed the query via Ollama
    emb = embed_text(query)
    emb_literal = _vector_to_pg_literal(emb)

    sql = """
        WITH query_vec AS (
            SELECT %s::vector AS embedding
        )
        SELECT
            ROW_NUMBER() OVER (ORDER BY (e.embedding <-> q.embedding)) AS rank,
            1.0 - (e.embedding <-> q.embedding) AS score, -- similarity ~ 1 - distance
            d.file_name,
            c.chunk_index,
            c.content
        FROM int.chunk_embeddings_development e
        JOIN int.chunks_development c
          ON c.chunk_id = e.chunk_id
        JOIN raw.documents_development d
          ON d.doc_id = c.doc_id
        CROSS JOIN query_vec q
        ORDER BY e.embedding <-> q.embedding
        LIMIT %s;
    """

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, (emb_literal, top_k))
                rows = cur.fetchall()
        return rows
    finally:
        conn.close()


# =====================================================
# 3) CLI / main
# =====================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Semantic search over development environment (pgvector + Ollama)."
    )
    parser.add_argument(
        "query",
        type=str,
        help="Search query text.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return.",
    )

    args = parser.parse_args()

    rows = search_development(args.query, top_k=args.top_k)

    if not rows:
        print("No results found.")
        return

    print(f"Top {len(rows)} results:\n")
    for rank, score, file_name, chunk_index, content in rows:
        preview = content[:200].replace("\n", " ")
        print("-" * 80)
        print(f"Rank       : {rank}")
        print(f"Score      : {score:.4f}")
        print(f"File       : {file_name}")
        print(f"Chunk index: {chunk_index}")
        print(f"Preview    : {preview!r}")


if __name__ == "__main__":
    main()
