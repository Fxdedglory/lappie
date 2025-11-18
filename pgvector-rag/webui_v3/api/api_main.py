"""
api_main.py
FastAPI wrapper around your existing RAG setup + chat history.

Version: v0.2.0 (2025-11-17)
echo: api_main.py v0.2.0 2025-11-17
"""

import os
from typing import List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

import psycopg2
from psycopg2.extras import Json
import uuid

# -------------------------------------------------------------------
# Load .env from this directory
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

# -------------------------------------------------------------------
# Ollama config
# -------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "ollama")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "gemma3:4b")

client = OpenAI(base_url=OLLAMA_BASE_URL, api_key=OLLAMA_API_KEY)

# -------------------------------------------------------------------
# Postgres connection
# -------------------------------------------------------------------
def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5433"),
        dbname=os.getenv("PGDATABASE", "chat_ingest"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
    )

# -------------------------------------------------------------------
# Chat History Helpers
# -------------------------------------------------------------------
def create_session() -> str:
    """Create a new chat session in chat_history.sessions."""
    session_id = str(uuid.uuid4())

    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chat_history.sessions (session_id)
        VALUES (%s)
        """,
        (session_id,),
    )
    conn.commit()
    cur.close()
    conn.close()

    return session_id


def insert_message(
    session_id: str,
    role: str,
    content: str,
    model_name: Optional[str] = None,
    token_count: Optional[int] = None,
    metadata=None,
):
    """Insert chat messages into chat_history.messages."""
    conn = get_pg_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO chat_history.messages
            (session_id, role, content, model_name, token_count, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            session_id,
            role,
            content,
            model_name,
            token_count,
            Json(metadata) if metadata else Json({}),
        ),
    )

    conn.commit()
    cur.close()
    conn.close()

# -------------------------------------------------------------------
# RAG Functions
# -------------------------------------------------------------------
def get_latest_doc_id(conn, source_name: str) -> str:
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

    results = []
    for content, metadata, score in rows:
        results.append((content, metadata, float(score)))
    return results


def synthesize_answer(question: str, chunks: List[Tuple[str, dict, float]]) -> str:
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
                    "You are a helpful assistant that answers questions ONLY about the ingested books. "
                    "Base answers strictly on the provided context; if not present, say you don't know."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Context from the book:\n\n{context_text}"
                ),
            },
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content.strip()


# -------------------------------------------------------------------
# FastAPI Models
# -------------------------------------------------------------------
class ChatRequest(BaseModel):
    question: str
    source_name: Optional[str] = "Fundamentals of Data Engineering"
    top_k: int = 5
    session_id: Optional[str] = None  # NEW


class ChunkInfo(BaseModel):
    content: str
    score: float
    chunk_idx: int


class ChatResponse(BaseModel):
    answer: str
    chunks: List[ChunkInfo]
    session_id: str  # NEW

class SessionSummaryModel(BaseModel):
    session_id: str
    started_at: str
    title: Optional[str] = None


class HistoryMessageModel(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None


# -------------------------------------------------------------------
# FastAPI App + Endpoint
# -------------------------------------------------------------------
app = FastAPI(title="webui_v3 RAG API")


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    # Create or reuse session
    session_id = req.session_id or create_session()

    # Store user question immediately
    insert_message(
        session_id=session_id,
        role="user",
        content=req.question,
        model_name=None,
    )

    conn = get_pg_connection()
    try:
        doc_id = get_latest_doc_id(conn, req.source_name)
        q_vec = embed_question(req.question)
        rows = search_chunks(conn, doc_id, q_vec, top_k=req.top_k)

        answer = synthesize_answer(req.question, rows)

        # Store assistant answer
        insert_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            model_name=OLLAMA_CHAT_MODEL,
            metadata={"chunks": rows},
        )

        chunk_infos = [
            ChunkInfo(
                content=content,
                score=score,
                chunk_idx=int(metadata.get("chunk_idx", -1)),
            )
            for content, metadata, score in rows
        ]

        return ChatResponse(
            answer=answer,
            chunks=chunk_infos,
            session_id=session_id,
        )

    finally:
        conn.close()
@app.get("/api/sessions", response_model=List[SessionSummaryModel])
def list_sessions(limit: int = 20):
    """
    Return recent chat sessions for the history sidebar.
    """
    conn = get_pg_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT session_id, started_at, title
            FROM chat_history.sessions
            ORDER BY started_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

        return [
            SessionSummaryModel(
                session_id=str(session_id),
                started_at=started_at.isoformat(),
                title=title,
            )
            for (session_id, started_at, title) in rows
        ]
    finally:
        conn.close()


@app.get(
    "/api/sessions/{session_id}/messages",
    response_model=List[HistoryMessageModel],
)
def get_session_messages(session_id: str):
    """
    Return all messages for a given session, oldest first.
    """
    conn = get_pg_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role, content, created_at
            FROM chat_history.messages
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        rows = cur.fetchall()

        return [
            HistoryMessageModel(
                role=role,
                content=content,
                created_at=created_at.isoformat() if created_at else None,
            )
            for (role, content, created_at) in rows
        ]
    finally:
        conn.close()
