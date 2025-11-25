# echo: pgvector-rag file_search_endpoints v0.1.0 2025-11-24

"""
FastAPI endpoints that expose the local file_searcher module.

Routes:
  POST /file-search/search
  POST /file-search/qa

These use:
  - pgvector search (search_development)
  - Ollama embeddings + chat (via file_searcher.embeddings / qa_development)
  - Optional LLM reranker (file_searcher.reranker)
"""

from __future__ import annotations

# =====================================================
# 1) Imports & sys.path wiring
# =====================================================

import sys
from pathlib import Path
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

# --- Make backend/file_searcher/src importable ---

# This file is at: <repo_root>/backend/api/file_search_endpoints.py
CURRENT_FILE = Path(__file__).resolve()
PGVECTOR_RAG_ROOT = CURRENT_FILE.parents[2]  # .../pgvector-rag
FILE_SEARCHER_SRC = PGVECTOR_RAG_ROOT / "backend" / "file_searcher" / "src"

if str(FILE_SEARCHER_SRC) not in sys.path:
    sys.path.append(str(FILE_SEARCHER_SRC))

# Now we can import the Python package defined in file_searcher/src/file_searcher
from file_searcher.search_development import search_development
from file_searcher.qa_development import (
    build_context_from_rows,
    build_prompt,
    call_ollama_chat,
)
from file_searcher.reranker import CandidateChunk, rerank_candidates


# =====================================================
# 2) Pydantic models
# =====================================================

class FileSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class FileSearchResult(BaseModel):
    rank: int
    score: float
    file_name: str
    chunk_index: int
    content: str


class FileSearchResponse(BaseModel):
    results: List[FileSearchResult]


class FileQARequest(BaseModel):
    question: str
    use_rerank: bool = True
    top_k_final: int = 5        # chunks used in context
    top_n_candidates: int = 15  # pgvector hits before rerank


class FileQAContextChunk(BaseModel):
    id: int
    orig_rank: int
    orig_score: float
    file_name: str
    chunk_index: int
    snippet: str


class FileQAResponse(BaseModel):
    answer: str
    context: List[FileQAContextChunk]


# =====================================================
# 3) Router and helpers
# =====================================================

router = APIRouter(prefix="/file-search", tags=["file-search"])


def _rows_to_results(rows) -> List[FileSearchResult]:
    """
    Convert raw rows from search_development into API models.

    rows: (rank, score, file_name, chunk_index, content)
    """
    results: List[FileSearchResult] = []
    for rank, score, file_name, chunk_index, content in rows:
        results.append(
            FileSearchResult(
                rank=rank,
                score=score,
                file_name=file_name,
                chunk_index=chunk_index,
                content=content,
            )
        )
    return results


# =====================================================
# 4) /file-search/search
# =====================================================

@router.post("/search", response_model=FileSearchResponse)
def file_search(req: FileSearchRequest) -> FileSearchResponse:
    """
    Semantic search over the development environment using pgvector.

    Thin wrapper around file_searcher.search_development.
    """
    rows = search_development(req.query, top_k=req.top_k)
    return FileSearchResponse(results=_rows_to_results(rows))


# =====================================================
# 5) /file-search/qa
# =====================================================

@router.post("/qa", response_model=FileQAResponse)
def file_search_qa(req: FileQARequest) -> FileQAResponse:
    """
    Q&A over the 'development' environment in file_searcher.

    If use_rerank=True:
      - Stage 1: pgvector search (top_n_candidates)
      - Stage 2: LLM reranker (reranker.py)
      - Build context from top_k_final reranked chunks

    If use_rerank=False:
      - Use simple top_k_final pgvector results as context.
    """
    # ----------------------------
    # Reranked path
    # ----------------------------
    if req.use_rerank:
        # Stage 1: pgvector search (more candidates up-front)
        rows = search_development(req.question, top_k=req.top_n_candidates)
        if not rows:
            return FileQAResponse(answer="No relevant context found.", context=[])

        # rows: (rank, score, file_name, chunk_index, content)
        candidates: List[CandidateChunk] = []
        for i, (rank, score, file_name, chunk_index, content) in enumerate(
            rows, start=1
        ):
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

        # Stage 2: rerank
        reranked = rerank_candidates(req.question, candidates)

        # Build fake 'rows' for the selected top_k_final chunks,
        # because build_context_from_rows expects the original tuple structure.
        selected = reranked[: req.top_k_final]
        fake_rows = [
            (c.rank, c.score, c.file_name, c.chunk_index, c.content)
            for c in selected
        ]
        context_str = build_context_from_rows(fake_rows)

        # Build answer
        prompt = build_prompt(req.question, context_str)
        answer = call_ollama_chat(prompt)

        # Build context payload for response
        context_chunks: List[FileQAContextChunk] = []
        for c in selected:
            snippet = c.content.strip().replace("\n", " ")
            if len(snippet) > 140:
                snippet = snippet[:140] + "..."
            context_chunks.append(
                FileQAContextChunk(
                    id=c.id,
                    orig_rank=c.rank,
                    orig_score=c.score,
                    file_name=c.file_name,
                    chunk_index=c.chunk_index,
                    snippet=snippet,
                )
            )

        return FileQAResponse(
            answer=answer.strip(),
            context=context_chunks,
        )

    # ----------------------------
    # Non-reranked path (simple)
    # ----------------------------
    rows = search_development(req.question, top_k=req.top_k_final)
    if not rows:
        return FileQAResponse(answer="No relevant context found.", context=[])

    context_str = build_context_from_rows(rows)
    prompt = build_prompt(req.question, context_str)
    answer = call_ollama_chat(prompt)

    context_chunks: List[FileQAContextChunk] = []
    for rank, score, file_name, chunk_index, content in rows:
        snippet = content.strip().replace("\n", " ")
        if len(snippet) > 140:
            snippet = snippet[:140] + "..."
        context_chunks.append(
            FileQAContextChunk(
                id=rank,
                orig_rank=rank,
                orig_score=score,
                file_name=file_name,
                chunk_index=chunk_index,
                snippet=snippet,
            )
        )

    return FileQAResponse(
        answer=answer.strip(),
        context=context_chunks,
    )
