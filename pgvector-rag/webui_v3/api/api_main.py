"""
api_main.py
FastAPI wrapper around your existing RAG setup.

Version: v0.1.0 (2025-11-17)
echo: api_main.py v0.1.0 2025-11-17
"""

import os
from typing import List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
import psycopg2

# Load .env from the same directory if present
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    # Fallback to process env (e.g. from your version_2 env)
    load_dotenv()

# Ollama / OpenAI-compatible client config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "gemma3:4b")

client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key=OLLAMA_API_KEY,
)


def get_pg_connection():
    """Create a psycopg2 connection using chat_ingest settings."""
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5433"),
        dbname=os.getenv("PGDATABASE", "chat_ingest"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
    )


def get_latest_doc_id(conn, source_name: str) -> str:
    """Return the latest doc_id for a given source_name from bronze.web_docs."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT doc_id
            FROM bronze.web_docs
            WHERE source_name = %s
            ORDER BY collected_at DESC, doc_id DESC
            LIMIT 1;
            """,
            (source_name,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(
                f"No bronze.web_docs row found for source_name={source_name!r}"
            )
        return str(row[0])


def embed_question(question: str) -> str:
    """Return a pgvector literal string for the question embedding."""
    resp = client.embeddings.create(
        model=OLLAMA_EMBED_MODEL,
        input=question,
    )
    emb = resp.data[0].embedding
    return "[" + ",".join(f"{x:.6f}" for x in emb) + "]"


def search_chunks(
    conn,
    doc_id: str,
    query_vector_literal: str,
    top_k: int = 5,
) -> List[Tuple[str, dict, float]]:
    """Return top-k chunks by similarity for a given doc_id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                content,
                metadata,
                1 - (embedding <=> %s::vector) AS score
            FROM vector.doc_chunks
            WHERE doc_id = %s::uuid
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
            """,
            (query_vector_literal, doc_id, query_vector_literal, top_k),
        )
        rows = cur.fetchall()

    results: List[Tuple[str, dict, float]] = []
    for content, metadata, score in rows:
        results.append((content, metadata, float(score)))
    return results


def synthesize_answer(question: str, chunks: List[Tuple[str, dict, float]]) -> str:
    """Use the chat model to synthesize an answer from retrieved chunks."""
    if not chunks:
        return "I couldn't find any relevant content in the book for that question."

    context_blocks = []
    for i, (content, metadata, score) in enumerate(chunks, start=1):
        idx = metadata.get("chunk_idx")
        meta_str = f"chunk_idx={idx}, score={score:.3f}"
        context_blocks.append(f"[Chunk {i} | {meta_str}]\n{content}")

    context_text = "\n\n".join(context_blocks)

    completion = client.chat.completions.create(
        model=OLLAMA_CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that answers questions ONLY "
                    "about the ingested books (starting with 'Fundamentals of Data Engineering'). "
                    "Base your answers strictly on the provided context; if the "
                    "answer is not in the context, say you don't know."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Context from the book (multiple chunks):\n\n{context_text}"
                ),
            },
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content.strip()


# ---------- FastAPI models & app ----------

class ChatRequest(BaseModel):
    question: str
    source_name: Optional[str] = "Fundamentals of Data Engineering"
    top_k: int = 5


class ChunkInfo(BaseModel):
    content: str
    score: float
    chunk_idx: int


class ChatResponse(BaseModel):
    answer: str
    chunks: List[ChunkInfo]


app = FastAPI(title="webui_v3 RAG API")


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Chat endpoint: ask a question about a given book/source."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    conn = get_pg_connection()
    try:
        doc_id = get_latest_doc_id(conn, req.source_name)
        q_vec = embed_question(req.question)
        rows = search_chunks(conn, doc_id, q_vec, top_k=req.top_k)

        answer = synthesize_answer(req.question, rows)

        chunk_infos: List[ChunkInfo] = []
        for content, metadata, score in rows:
            idx = int(metadata.get("chunk_idx", -1))
            chunk_infos.append(
                ChunkInfo(content=content, score=score, chunk_idx=idx)
            )

        return ChatResponse(answer=answer, chunks=chunk_infos)
    finally:
        conn.close()
