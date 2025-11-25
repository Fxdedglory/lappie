# echo: file_searcher qa_development v0.1.0 2025-11-24

"""
Q&A over the development environment using local Ollama.

Flow:
  1) Take a user question
  2) Run semantic search over development (pgvector)
  3) Build a context block from top-k chunks
  4) Call Ollama chat model with CONTEXT + QUESTION
  5) Print answer + simple citations

Sections:
  1) Imports & config
  2) Search + context formatting
  3) Ollama chat client
  4) Q&A pipeline
  5) CLI / main
"""

# =====================================================
# 1) Imports & config
# =====================================================

from __future__ import annotations

import argparse
import os
from typing import List, Tuple

import requests
from dotenv import load_dotenv

from .search_development import search_development


def _load_chat_config() -> dict:
    """
    Load Ollama chat config from .env.

    Expected keys (with defaults):
      OLLAMA_BASE_URL    (default: http://localhost:11434)
      OLLAMA_CHAT_MODEL  (default: llama3.2)

    Returns:
        dict with base_url and model
    """
    load_dotenv()

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")

    return {
        "base_url": base_url.rstrip("/"),
        "model": model,
    }


# =====================================================
# 2) Search + context formatting
# =====================================================

def build_context_from_rows(
    rows: List[Tuple],
    *,
    max_chars_per_chunk: int = 700,
) -> str:
    """
    Turn search results into a context string for the LLM.

    Each row from search_development is:
      (rank, score, file_name, chunk_index, content)
    """
    blocks: List[str] = []
    for rank, score, file_name, chunk_index, content in rows:
        snippet = content.strip().replace("\n", " ")
        if len(snippet) > max_chars_per_chunk:
            snippet = snippet[:max_chars_per_chunk] + "..."

        block = (
            f"[{rank}] (score={score:.3f}, file={file_name}, chunk={chunk_index})\n"
            f"{snippet}"
        )
        blocks.append(block)

    return "\n\n".join(blocks)


def build_prompt(question: str, context: str) -> str:
    """
    Build the final prompt sent to the chat model.
    """
    return f"""You are a helpful assistant answering questions about documents.

Use ONLY the information in the CONTEXT below to answer the QUESTION.
If the answer is not clearly contained in the context, say you do not know.

CONTEXT:
{context}

QUESTION:
{question}

Answer concisely in a few sentences.
"""


# =====================================================
# 3) Ollama chat client
# =====================================================

def call_ollama_chat(prompt: str) -> str:
    """
    Call Ollama's /api/chat endpoint with a single user prompt.

    Returns:
        The assistant's response text.

    Raises:
        RuntimeError if the request fails.
    """
    cfg = _load_chat_config()
    url = f"{cfg['base_url']}/api/chat"

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }

    try:
        resp = requests.post(url, json=payload, timeout=120)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Failed to connect to Ollama at {url}. "
            f"Is 'ollama serve' running and is the chat model pulled? "
            f"Original error: {e}"
        ) from e

    if resp.status_code != 200:
        raise RuntimeError(
            f"Ollama chat request failed: {resp.status_code} {resp.text}"
        )

    data = resp.json()
    # Expected shape: { "message": { "role": "assistant", "content": "..." }, ... }
    msg = data.get("message") or {}
    content = msg.get("content")
    if not content:
        raise RuntimeError(f"Ollama chat response missing content: {data}")

    return content


# =====================================================
# 4) Q&A pipeline
# =====================================================

def answer_question(question: str, *, top_k: int = 5) -> None:
    """
    High-level Q&A pipeline over the development environment.

    Steps:
      1) semantic search
      2) build context
      3) call chat model
      4) print answer + citations
    """
    rows = search_development(question, top_k=top_k)

    if not rows:
        print("No relevant context found for this question.")
        return

    context = build_context_from_rows(rows)
    prompt = build_prompt(question, context)
    answer = call_ollama_chat(prompt)

    # Print answer
    print("=== ANSWER ===")
    print(answer.strip())
    print()

    # Print lightweight citations
    print("=== CONTEXT (top results) ===")
    for rank, score, file_name, chunk_index, content in rows:
        snippet = content.strip().replace("\n", " ")
        snippet = snippet[:140] + ("..." if len(snippet) > 140 else "")
        print("-" * 80)
        print(f"[{rank}] score={score:.3f} file={file_name} chunk={chunk_index}")
        print(f"snippet: {snippet!r}")


# =====================================================
# 5) CLI / main
# =====================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Q&A over development environment using local Ollama + pgvector."
    )
    parser.add_argument(
        "question",
        type=str,
        help="Question to ask over the indexed documents.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of context chunks to retrieve.",
    )

    args = parser.parse_args()
    answer_question(args.question, top_k=args.top_k)


if __name__ == "__main__":
    main()
