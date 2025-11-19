"""
api_main.py
FastAPI wrapper around your existing RAG setup + chat history.

Version: v0.3.0 (2025-11-17)
echo: api_main.py v0.3.0 2025-11-17
"""

import os
import math
import uuid
from typing import List, Optional, Tuple, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

import psycopg2
from psycopg2.extras import Json


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


def get_embedding_vector(text: str) -> list[float]:
    """
    Return the raw embedding vector (list of floats) for a given text.

    This is used both for:
    - pgvector searches (via embed_question)
    - debugging / embedding browser tools
    """
    resp = client.embeddings.create(
        model=OLLAMA_EMBED_MODEL,
        input=text,
    )
    return list(resp.data[0].embedding)


def embed_question(question: str) -> str:
    """
    Return a pgvector literal string for the question embedding,
    e.g. '[0.123456,0.234567,...]'.
    """
    emb = get_embedding_vector(question)
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

    results: List[Tuple[str, dict, float]] = []
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


def rerank_chunks_with_llm(
    question: str,
    chunks: List[Tuple[str, dict, float]],
) -> List[Tuple[str, dict, float, float]]:
    """
    Given (content, metadata, base_score) from vector search,
    call the chat model once to assign rerank scores in [0, 1].

    Returns a list of (content, metadata, base_score, rerank_score),
    sorted by rerank_score descending.
    """
    if not chunks:
        return []

    # Build a compact preview to avoid huge prompts
    lines = []
    for i, (content, metadata, base_score) in enumerate(chunks, start=1):
        preview = content.replace("\n", " ")
        if len(preview) > 400:
            preview = preview[:400] + "..."
        lines.append(
            f"Chunk {i} (base_score={base_score:.3f}, "
            f"chunk_idx={metadata.get('chunk_idx', -1)}): {preview}"
        )

    context = "\n".join(lines)

    system_msg = (
        "You are a reranking helper. Given a question and a list of text chunks, "
        "assign a relevance score between 0.0 and 1.0 to EACH chunk.\n"
        "Higher score = more relevant to the question.\n"
        "Return your answer as one line per chunk in the exact format:\n"
        "index score\n"
        "For example, if there are 3 chunks, you might return:\n"
        "1 0.92\n"
        "2 0.15\n"
        "3 0.40\n"
        "Do not include any other text."
    )

    user_msg = (
        f"Question:\n{question}\n\n"
        f"Chunks:\n{context}\n\n"
        "Now return the scores."
    )

    completion = client.chat.completions.create(
        model=OLLAMA_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
    )

    text = completion.choices[0].message.content.strip()
    # Parse lines like "1 0.92"
    scores_by_index: dict[int, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            idx = int(parts[0])
            score = float(parts[1])
            scores_by_index[idx] = max(0.0, min(1.0, score))
        except ValueError:
            continue

    # Fallback: if parsing failed, just mirror base scores
    if not scores_by_index:
        return [
            (content, metadata, base_score, base_score)
            for (content, metadata, base_score) in chunks
        ]

    reranked: List[Tuple[str, dict, float, float]] = []
    for i, (content, metadata, base_score) in enumerate(chunks, start=1):
        rerank_score = scores_by_index.get(i, base_score)
        reranked.append((content, metadata, base_score, rerank_score))

    # Sort by rerank_score desc
    reranked.sort(key=lambda x: x[3], reverse=True)
    return reranked


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


# ---------- Tooling: SQL helper models ----------
class SqlRequest(BaseModel):
    query: str


class SqlResponse(BaseModel):
    # Now rows are dicts keyed by column name, so the frontend can do row[col]
    rows: list[dict[str, Any]]
    columns: list[str]


class ChunkViewRequest(BaseModel):
    question: str
    source_name: Optional[str] = "Fundamentals of Data Engineering"
    top_k: int = 5


class ChunkViewResponse(BaseModel):
    chunks: List[ChunkInfo]


# ---------- Reranker debug models ----------
class RerankChunksRequest(BaseModel):
    question: str
    source_name: Optional[str] = "Fundamentals of Data Engineering"
    top_k: int = 5


class RerankChunk(BaseModel):
    content: str
    base_score: float
    rerank_score: float
    chunk_idx: int


class RerankChunksResponse(BaseModel):
    chunks: List[RerankChunk]


# ---------- Embedding debug models ----------
class EmbeddingToolRequest(BaseModel):
    text: str


class EmbeddingToolResponse(BaseModel):
    dimension: int
    norm: float
    vector: list[float]


# -------------------------------------------------------------------
# FastAPI App + Endpoints
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


@app.post("/api/tools/sql", response_model=SqlResponse)
def run_sql_tool(req: SqlRequest):
    """
    Very simple, read-only SQL helper.

    - Only allows queries starting with SELECT (case-insensitive).
    - No semicolons allowed (single statement only).
    - Runs against chat_ingest via get_pg_connection().
    """
    q = req.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    # Basic safety checks
    if ";" in q:
        raise HTTPException(
            status_code=400,
            detail="Multiple statements / semicolons are not allowed.",
        )

    if not q.lower().startswith("select"):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT queries are allowed in this endpoint.",
        )

    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(q)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
    finally:
        conn.close()

    # Convert rows (tuples) into dicts keyed by column name
    list_rows: list[dict[str, Any]] = []
    for row in rows:
        obj: dict[str, Any] = {}
        for col_name, value in zip(columns, row):
            obj[col_name] = value
        list_rows.append(obj)

    return SqlResponse(rows=list_rows, columns=columns)


@app.post("/api/tools/chunks", response_model=ChunkViewResponse)
def view_chunks(req: ChunkViewRequest):
    """
    Debug endpoint: return the raw top-k chunks for a question,
    without LLM synthesis. Useful for checking retrieval quality.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    conn = get_pg_connection()
    try:
        doc_id = get_latest_doc_id(conn, req.source_name)
        q_vec = embed_question(req.question)
        rows = search_chunks(conn, doc_id, q_vec, top_k=req.top_k)

        chunk_infos: List[ChunkInfo] = []
        for content, metadata, score in rows:
            idx = int(metadata.get("chunk_idx", -1))
            chunk_infos.append(
                ChunkInfo(
                    content=content,
                    score=score,
                    chunk_idx=idx,
                )
            )

        return ChunkViewResponse(chunks=chunk_infos)
    finally:
        conn.close()


@app.post("/api/tools/chunks_rerank", response_model=RerankChunksResponse)
def debug_chunks_rerank(req: RerankChunksRequest):
    """
    Debug endpoint: run vector search, then rerank chunks with the LLM.
    Returns both base_score (vector similarity) and rerank_score.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    conn = get_pg_connection()
    try:
        doc_id = get_latest_doc_id(conn, req.source_name)
        q_vec = embed_question(req.question)
        base_rows = search_chunks(conn, doc_id, q_vec, top_k=req.top_k)
    finally:
        conn.close()

    if not base_rows:
        return RerankChunksResponse(chunks=[])

    reranked = rerank_chunks_with_llm(req.question, base_rows)

    payload: List[RerankChunk] = []
    for content, metadata, base_score, rerank_score in reranked:
        idx = int(metadata.get("chunk_idx", -1))
        payload.append(
            RerankChunk(
                content=content,
                base_score=base_score,
                rerank_score=rerank_score,
                chunk_idx=idx,
            )
        )

    return RerankChunksResponse(chunks=payload)


@app.post("/api/tools/embedding", response_model=EmbeddingToolResponse)
def run_embedding_tool(req: EmbeddingToolRequest):
    """
    Debug endpoint: return the raw embedding vector for a given text,
    along with its dimension and L2 norm.
    """
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text must not be empty.")

    vec = get_embedding_vector(text)
    norm = math.sqrt(sum(x * x for x in vec))

    return EmbeddingToolResponse(
        dimension=len(vec),
        norm=norm,
        vector=vec,
    )
