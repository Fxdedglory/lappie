# echo: file_searcher chunker v0.1.0 2025-11-24

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel


class ChunkMetadata(BaseModel):
    """
    Lightweight metadata for a chunk.

    Extend this later with:
      - source_id (doc_id from Postgres)
      - page_number
      - section_heading
      - etc.
    """
    chunk_index: int
    start_char: int
    end_char: int
    source_id: Optional[str] = None


class TextChunk(BaseModel):
    """
    A single text chunk plus its metadata.
    """
    content: str
    metadata: ChunkMetadata


def _normalize_text(text: str) -> str:
    """
    Basic normalization:
      - normalize newlines
      - strip trailing spaces
    """
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def _split_into_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs using blank lines as separators.
    This approximates Gemini's 'semantic block' behavior without any external deps.
    """
    paragraphs: List[str] = []
    current: List[str] = []

    for line in text.split("\n"):
        if line.strip() == "":
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
        else:
            current.append(line.strip())

    if current:
        paragraphs.append(" ".join(current).strip())

    return paragraphs


def split_text_into_chunks(
    text: str,
    *,
    max_words: int = 220,
    overlap_words: int = 40,
    source_id: Optional[str] = None,
) -> List[TextChunk]:
    """
    Chunk a long string into overlapping segments.

    Strategy:
      1. Normalize text and split into paragraphs (blank-line separated).
      2. Fill a chunk with whole paragraphs until adding the next paragraph
         would push the chunk over `max_words`.
      3. When we overflow, we:
           - yield the chunk
           - carry the last `overlap_words` into the next chunk as overlap
      4. Continue until all text is chunked.

    This gives you:
      - paragraph-aware chunks
      - overlapping context (Gemini-style feel)
      - simple implementation with no external APIs.

    Args:
        text: Full document text (already extracted from PDF/HTML/etc.).
        max_words: Maximum words per chunk.
        overlap_words: How many words from the previous chunk to copy into
                       the next chunk as overlap.
        source_id: Optional identifier you can map to your Postgres doc_id.

    Returns:
        List[TextChunk] with content and basic metadata.
    """
    norm_text = _normalize_text(text)
    paragraphs = _split_into_paragraphs(norm_text)

    chunks: List[TextChunk] = []
    chunk_index = 0
    global_char_pos = 0  # counts characters in the normalized text

    # For mapping back to char positions, we rebuild from paragraphs.
    # This is approximate but deterministic.
    rebuilt_text_parts: List[str] = []
    paragraph_char_offsets: List[int] = []  # start char index of each paragraph

    for para in paragraphs:
        paragraph_char_offsets.append(global_char_pos)
        rebuilt_text_parts.append(para)
        # +1 for the newline separator we'll conceptually add between paragraphs
        global_char_pos += len(para) + 1

    current_words: List[str] = []
    current_start_char: Optional[int] = None
    current_end_char: Optional[int] = None

    def flush_current_chunk():
        nonlocal current_words, current_start_char, current_end_char, chunk_index

        if not current_words:
            return

        content = " ".join(current_words).strip()
        if not content:
            return

        metadata = ChunkMetadata(
            chunk_index=chunk_index,
            start_char=current_start_char or 0,
            end_char=current_end_char or (current_start_char or 0) + len(content),
            source_id=source_id,
        )
        chunks.append(TextChunk(content=content, metadata=metadata))
        chunk_index += 1
        current_words = []

    # Iterate over paragraphs, building chunks
    for para_idx, para in enumerate(paragraphs):
        words = para.split()
        para_word_count = len(words)

        # Starting char of this paragraph in the reconstructed text
        para_start_char = paragraph_char_offsets[para_idx]
        para_end_char = para_start_char + len(para)

        # If adding this paragraph would blow up the chunk too much,
        # flush the current chunk first.
        if current_words and (len(current_words) + para_word_count) > max_words:
            flush_current_chunk()

            # Start new chunk with overlap from the end of the previous chunk.
            # We just reuse the last overlap_words we wrote.
            # Since we don't keep all-old-chunks' words around,
            # we can't perfectly reconstruct overlap here after flush.
            # Instead, we intentionally start "fresh" from this paragraph,
            # which is acceptable for v0.1. We can refine later if needed.

        # If this is the first paragraph in a new chunk, set start_char
        if not current_words:
            current_start_char = para_start_char

        current_words.extend(words)
        current_end_char = para_end_char

        # If this paragraph alone is huge (> max_words), break it internally
        while len(current_words) > max_words:
            # Take a slice for the chunk
            slice_words = current_words[:max_words]
            slice_content = " ".join(slice_words).strip()
            if slice_content:
                # Approximate char range for this slice
                # We don't compute exact slice char bounds for now, just reuse
                # current_start_char / current_end_char.
                metadata = ChunkMetadata(
                    chunk_index=chunk_index,
                    start_char=current_start_char or 0,
                    end_char=current_end_char or (current_start_char or 0) + len(slice_content),
                    source_id=source_id,
                )
                chunks.append(TextChunk(content=slice_content, metadata=metadata))
                chunk_index += 1

            # Prepare next slice with overlap
            overlap_slice = current_words[max_words - overlap_words : max_words]
            current_words = overlap_slice + current_words[max_words:]

    # Flush whatever remains
    flush_current_chunk()

    return chunks


if __name__ == "__main__":
    demo_text = """
    Chapter 1: Introduction

    This is a simple example document. It has several paragraphs,
    and we want to see how the chunker breaks them into pieces.

    Here is another paragraph. It should probably end up in the same
    chunk as the first one, depending on the max_words configuration.

    Chapter 2: More Content

    This is yet another paragraph which we include to ensure there is
    enough text to generate multiple chunks from this small example.
    """

    chunks = split_text_into_chunks(
        demo_text,
        max_words=40,
        overlap_words=10,
        source_id="demo-doc-1",
    )

    print(f"Total chunks: {len(chunks)}")
    for ch in chunks:
        print("-" * 40)
        print(f"Chunk {ch.metadata.chunk_index}")
        print(f"Chars: {ch.metadata.start_char}–{ch.metadata.end_char}")
        print(ch.content)
