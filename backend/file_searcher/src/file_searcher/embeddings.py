# file_searcher/embeddings.py
# echo: embeddings v0.2.0 2025-11-24

import os
from typing import List

import requests

# Base URL for Ollama – we normalize it and strip any `/v1` suffix
_raw_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
_raw_base = _raw_base.rstrip("/")
if _raw_base.endswith("/v1"):
    _raw_base = _raw_base[:-3]  # drop trailing "/v1"

OLLAMA_BASE_URL = _raw_base
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def _embed_ollama_batch(texts: List[str]) -> List[List[float]]:
    """
    Call Ollama's /api/embeddings endpoint once per text.
    Returns a list of embedding vectors (list of floats) – suitable for pgvector.
    """
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    embeddings: List[List[float]] = []

    for text in texts:
        payload = {
            "model": OLLAMA_EMBED_MODEL,
            "prompt": text,
        }
        resp = requests.post(url, json=payload, timeout=60)

        if resp.status_code != 200:
            raise RuntimeError(
                f"Ollama embed request failed: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        # Ollama returns {"embedding": [...]} for embeddings
        emb = data.get("embedding")
        if emb is None:
            raise RuntimeError(
                f"Ollama embed response missing 'embedding' field: {data}"
            )

        embeddings.append(emb)

    return embeddings


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Public API used by search_development.py etc.
    """
    return _embed_ollama_batch(texts)


def embed_text(text: str) -> List[float]:
    """
    Convenience wrapper for a single text.
    """
    return embed_texts([text])[0]
