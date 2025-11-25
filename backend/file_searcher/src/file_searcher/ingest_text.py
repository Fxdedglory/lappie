# echo: file_searcher ingest_text v0.1.0 2025-11-24

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from .chunker import split_text_into_chunks, TextChunk


def ingest_text(
    text: str,
    *,
    source_id: Optional[str] = None,
    max_words: int = 220,
    overlap_words: int = 40,
) -> List[TextChunk]:
    """
    High-level ingest function that:
      - takes raw text
      - uses the Gemini-style chunker
      - returns a list of TextChunk objects

    Later, this is where we'll:
      - call Ollama for embeddings
      - insert chunks + embeddings into Postgres/pgvector
    """
    return split_text_into_chunks(
        text,
        max_words=max_words,
        overlap_words=overlap_words,
        source_id=source_id,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a text file and print chunk summaries."
    )
    parser.add_argument(
        "path",
        type=str,
        help="Path to a .txt file to ingest.",
    )
    parser.add_argument(
        "--source-id",
        type=str,
        default=None,
        help="Optional source identifier (e.g., doc_id).",
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
    if not file_path.is_file():
        raise SystemExit(f"File not found: {file_path}")

    text = file_path.read_text(encoding="utf-8", errors="ignore")
    chunks = ingest_text(
        text,
        source_id=args.source_id or file_path.name,
        max_words=args.max_words,
        overlap_words=args.overlap_words,
    )

    print(f"Source: {args.source_id or file_path.name}")
    print(f"Total chunks: {len(chunks)}")
    print()

    for ch in chunks:
        meta = ch.metadata
        preview = ch.content[:200].replace("\n", " ")
        print("-" * 60)
        print(f"Chunk {meta.chunk_index}")
        print(f"Chars: {meta.start_char}–{meta.end_char}")
        print(f"Source ID: {meta.source_id}")
        print(f"Preview: {preview!r}")


if __name__ == "__main__":
    main()
