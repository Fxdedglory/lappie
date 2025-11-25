# echo: file_searcher reranker v0.1.0 2025-11-24

"""
LLM-based reranker for search candidates.

Used as a second stage after pgvector:
  - Stage 1: pgvector returns top-N candidates by embedding similarity
  - Stage 2: reranker asks an LLM to reorder them by semantic relevance

Sections:
  1) Imports & types
  2) Prompt builder
  3) LLM call (reuse qa_development call_ollama_chat)
  4) Rerank function (public API)
"""

# =====================================================
# 1) Imports & types
# =====================================================

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

from .qa_development import call_ollama_chat


@dataclass
class CandidateChunk:
    """
    Represents a single search candidate chunk for reranking.
    """
    id: int               # local ID for reranker (1..N)
    rank: int             # original pgvector rank
    score: float          # original pgvector similarity
    file_name: str
    chunk_index: int
    content: str


# =====================================================
# 2) Prompt builder
# =====================================================

def build_rerank_prompt(question: str, candidates: List[CandidateChunk]) -> str:
    """
    Build a prompt instructing the LLM to rerank candidates.

    We ask it to return a JSON list of candidate IDs in best-first order, e.g.:
      [1, 3, 2]
    """
    blocks = []
    for c in candidates:
        snippet = c.content.strip().replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400] + "..."
        block = (
            f"ID: {c.id}\n"
            f"OriginalRank: {c.rank}\n"
            f"OriginalScore: {c.score:.3f}\n"
            f"File: {c.file_name}\n"
            f"ChunkIndex: {c.chunk_index}\n"
            f"Text: {snippet}\n"
        )
        blocks.append(block)

    candidates_text = "\n\n".join(blocks)

    prompt = f"""You are a reranking assistant.

You are given a QUESTION and a list of CANDIDATE text chunks.
Your task is to rank the chunks from most relevant to least relevant to answer the QUESTION.

Return ONLY a JSON array of candidate IDs in best-first order.
Do NOT include any other text.
Example: [3, 1, 2]

QUESTION:
{question}

CANDIDATES:
{candidates_text}
"""

    return prompt


# =====================================================
# 3) LLM call + JSON parsing
# =====================================================

def _parse_id_list(raw: str, max_id: int) -> List[int]:
    """
    Parse a JSON list of integers from the model's response.

    If parsing fails or the result is invalid, fallback to [1, 2, ..., max_id].
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("Expected a list")

        ids: List[int] = []
        for item in data:
            if isinstance(item, int) and 1 <= item <= max_id:
                ids.append(item)

        if not ids:
            raise ValueError("Empty or invalid ID list")

        # Remove duplicates while preserving order
        seen = set()
        unique_ids: List[int] = []
        for i in ids:
            if i not in seen:
                seen.add(i)
                unique_ids.append(i)

        return unique_ids
    except Exception:
        # Fallback: identity ordering
        return list(range(1, max_id + 1))


# =====================================================
# 4) Public API: rerank_candidates
# =====================================================

def rerank_candidates(
    question: str,
    candidates: List[CandidateChunk],
) -> List[CandidateChunk]:
    """
    Rerank candidates using an LLM.

    Args:
        question: The user question.
        candidates: List of CandidateChunk from pgvector stage.

    Returns:
        New list of CandidateChunk in reranked order.
    """
    if not candidates:
        return []

    prompt = build_rerank_prompt(question, candidates)
    # Reuse the same Ollama chat client used for Q&A
    raw_response = call_ollama_chat(prompt)

    id_order = _parse_id_list(raw_response, max_id=len(candidates))

    # Build a lookup by local ID
    by_id = {c.id: c for c in candidates}

    # Reorder according to id_order, ignoring any IDs that don't exist
    reranked: List[CandidateChunk] = []
    for cid in id_order:
        c = by_id.get(cid)
        if c is not None:
            reranked.append(c)

    # If for some reason we lost items, append any remaining in original order
    if len(reranked) < len(candidates):
        remaining = [c for c in candidates if c not in reranked]
        reranked.extend(remaining)

    return reranked
