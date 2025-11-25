# echo: file_searcher multi_ingest_development v0.1.0 2025-11-24

"""
Multi-file ingestion into the development environment.

Flow (per file):
  1) ingest_file_to_development:
       - raw.documents_development
       - stg.document_text_development
       - int.chunks_development
  2) embed_development_chunks:
       - int.chunk_embeddings_development

Idempotent:
  - Re-running on the same files reuses doc_id, overwrites text, chunks, and embeddings.

Sections:
  1) Imports & config
  2) File discovery
  3) Per-file processing
  4) CLI / main
"""

# =====================================================
# 1) Imports & config
# =====================================================

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

from .ingest_file_to_development import ingest_file_to_development
from .embed_development_chunks import embed_chunks_for_file


# =====================================================
# 2) File discovery
# =====================================================

def discover_files(
    root: Path,
    patterns: Iterable[str],
    *,
    recursive: bool = True,
) -> List[Path]:
    """
    Discover files under root matching any of the glob patterns.

    Args:
        root: Root directory to search.
        patterns: e.g. ["*.txt", "*.md"]
        recursive: If True, use rglob; else plain glob.

    Returns:
        Sorted list of Path objects.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"Root is not a directory: {root}")

    files: set[Path] = set()
    for pattern in patterns:
        if recursive:
            files.update(root.rglob(pattern))
        else:
            files.update(root.glob(pattern))

    return sorted(files)


# =====================================================
# 3) Per-file processing
# =====================================================

def process_file(path: Path) -> Tuple[bool, str]:
    """
    Process a single file:
      - ingest to development
      - embed chunks for that file

    Returns:
        (success_flag, message)
    """
    try:
        ingest_file_to_development(
            file_path=path,
            mime_type="text/plain",  # adjust later if you add PDF/HTML support
            max_words=220,
            overlap_words=40,
        )

        embed_chunks_for_file(path)
        return True, f"OK: {path}"
    except Exception as e:  # noqa: BLE001
        return False, f"ERROR: {path} -> {e}"


def multi_ingest(
    root: Path,
    *,
    patterns: List[str],
    limit: int | None = None,
    recursive: bool = True,
) -> None:
    """
    High-level multi-file ingestion pipeline.

    Steps:
      1) Discover files under root matching patterns
      2) Optionally limit count
      3) For each file:
           - ingest + embed
           - log result
      4) Print summary
    """
    files = discover_files(root, patterns, recursive=recursive)
    if limit is not None:
        files = files[:limit]

    if not files:
        print(f"No files found under {root} for patterns={patterns}")
        return

    print(f"Discovered {len(files)} file(s) under {root}")
    successes = 0
    failures = 0

    for idx, path in enumerate(files, start=1):
        print(f"[{idx}/{len(files)}] Processing: {path}")
        ok, msg = process_file(path)
        print(f"    {msg}")

        if ok:
            successes += 1
        else:
            failures += 1

    print()
    print("=== SUMMARY ===")
    print(f"Root      : {root}")
    print(f"Patterns  : {patterns}")
    print(f"Processed : {len(files)}")
    print(f"Successes : {successes}")
    print(f"Failures  : {failures}")


# =====================================================
# 4) CLI / main
# =====================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-file ingestion into development (ingest + embed)."
    )
    parser.add_argument(
        "root",
        type=str,
        help="Root directory containing files to ingest (e.g. E:\\lappie\\Library).",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        default=None,
        help="Glob pattern(s) to include (e.g. --pattern *.txt --pattern *.pdf). "
             "Can be specified multiple times. Default: *.txt, *.pdf",

    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="If set, do not search subdirectories (use glob instead of rglob).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of files to process.",
    )

    args = parser.parse_args()
    root = Path(args.root)

    patterns = args.patterns or ["*.txt", "*.pdf"]

    multi_ingest(
        root=root,
        patterns=patterns,
        limit=args.limit,
        recursive=not args.no_recursive,
    )


if __name__ == "__main__":
    main()
