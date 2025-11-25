# echo: file_searcher qa_development_rerank v0.1.0 2025-11-24

"""
Q&A over development environment with LLM-based reranking.

Flow:
  1) pgvector search: get top-N candidates (fast similarity)
  2) LLM reranker: reorder candidates by semantic relevance
  3) Build context from top-K reranked chunks
  4) Call Ollama chat to answer question using that context
  5) Print answer + citations

Sections:
  1) Imports & config
  2) Context building
  3) Q&A pipeline with rerank
  4) CLI / main
"""

# =====================================================
# 1) Imports & config
# =====================================================

from __future__ import annotations

import argparse
from typing import List, Tuple

from .search_development import search_development
from .qa_development import build_prompt, call_ollama_chat
from .reranker import CandidateChunk, rerank_candidates


# =====================================================
# 2) Context building
# =====================================================

def build_context_from_reranked(
    reranked: List[CandidateChunk],
    *,
    max_context_chunks: int = 5,
    max_chars_per_chunk: int = 700,
) -> str:
    """
    Build context string from reranked candidate chunks.
    """
    selected = reranked[:max_context_chunks]

    blocks = []
    for c in selected:
        snippet = c.content.strip().replace("\n", " ")
        if len(snippet) > max_chars_per_chunk:
            snippet = snippet[:max_chars_per_chunk] + "..."

        block = (
            f"[{c.id}] (orig_rank={c.rank}, orig_score={c.score:.3f}, "
            f"file={c.file_name}, chunk={c.chunk_index})\n"
            f"{snippet}"
        )
        blocks.append(block)

    return "\n\n".join(blocks), selected


# =====================================================
# 3) Q&A pipeline with rerank
# =====================================================

def answer_question_with_rerank(
    question: str,
    *,
    top_k_final: int = 5,
    top_n_candidates: int = 15,
) -> None:
    """
    High-level Q&A pipeline with reranking.

    Args:
        question: User question string.
        top_k_final: Number of reranked chunks to use for context.
        top_n_candidates: Number of candidates to pull from pgvector before reranking.
    """
    # 1) Stage 1: pgvector search
    rows: List[Tuple] = search_development(question, top_k=top_n_candidates)

    if not rows:
        print("No relevant context found for this question.")
        return

    # rows: (rank, score, file_name, chunk_index, content)
    candidates: List[CandidateChunk] = []
    for i, (rank, score, file_name, chunk_index, content) in enumerate(rows, start=1):
        candidates.append(
            CandidateChunk(
                id=i,
                rank=rank,
                score=score,
                file_name=file_name,
                chunk_index=chunk_index,
                content=content,
            )
        )

    # 2) Stage 2: LLM reranker
    reranked = rerank_candidates(question, candidates)

    # 3) Build context from top-K reranked chunks
    context, selected = build_context_from_reranked(
        reranked,
        max_context_chunks=top_k_final,
    )
    prompt = build_prompt(question, context)

    # 4) Call chat model
    answer = call_ollama_chat(prompt)

    print("=== ANSWER (with rerank) ===")
    print(answer.strip())
    print()

    print("=== CONTEXT (reranked top chunks) ===")
    for c in selected:
        snippet = c.content.strip().replace("\n", " ")
        snippet = snippet[:140] + ("..." if len(snippet) > 140 else "")
        print("-" * 80)
        print(
            f"[{c.id}] orig_rank={c.rank} orig_score={c.score:.3f} "
            f"file={c.file_name} chunk={c.chunk_index}"
        )
        print(f"snippet: {snippet!r}")


# =====================================================
# 4) CLI / main
# =====================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Q&A over development environment with LLM-based reranking."
    )
    parser.add_argument(
        "question",
        type=str,
        help="Question to ask over the indexed documents.",
    )
    parser.add_argument(
        "--top-k-final",
        type=int,
        default=5,
        help="Number of reranked chunks to include in context.",
    )
    parser.add_argument(
        "--top-n-candidates",
        type=int,
        default=15,
        help="Number of pgvector candidates before reranking.",
    )

    args = parser.parse_args()
    answer_question_with_rerank(
        args.question,
        top_k_final=args.top_k_final,
        top_n_candidates=args.top_n_candidates,
    )


if __name__ == "__main__":
    main()
