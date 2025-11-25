# api_main.py
# echo: api_main v0.8.0 2025-11-24

import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Any, Dict, Tuple
from datetime import datetime
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import psycopg2
from psycopg2.extensions import connection as PGConnection

# ---------------------------------------------------------
# Environment & paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

# Load .env from backend/api/.env
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)

# Where the file_searcher Python package lives
DEFAULT_FILE_SEARCHER_SRC = ROOT_DIR / "file_searcher" / "src"
FILE_SEARCHER_SRC = Path(
    os.getenv("FILE_SEARCHER_SRC_ROOT", str(DEFAULT_FILE_SEARCHER_SRC))
)

# Make sure Python can import the local file_searcher package
if str(FILE_SEARCHER_SRC) not in sys.path:
    sys.path.insert(0, str(FILE_SEARCHER_SRC))

# Now that sys.path is ready, import file_searcher modules
from file_searcher.search_development import search_development
from file_searcher.qa_development import (
    build_context_from_rows,
    build_prompt,
    call_ollama_chat,
)

# Default library directory (can override via LIBRARY_DIR in .env)
DEFAULT_LIBRARY_DIR = Path(os.getenv("LIBRARY_DIR", r"E:\lappie\Library"))


def get_pg_connection() -> PGConnection:
    """
    Connect to the Postgres instance used by file_searcher + chat_history.
    Respects .env, with default matching your local setup.
    """
    host = os.getenv("PGHOST", "localhost")
    dbname = os.getenv("PGDATABASE", "file_searcher")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "postgres")

    # Default to port 5433 (your file_searcher DB), not 5432.
    try:
        port = int(os.getenv("PGPORT", "5433"))
    except ValueError:
        port = 5433

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )


# ---------------------------------------------------------
# Direct RAG via file_searcher.search_development + qa_development helpers
# ---------------------------------------------------------


def run_rag_chat(question: str, top_k: int = 5) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Real RAG pipeline wired directly into file_searcher:

    1) Uses search_development() to fetch top_k chunks from your dev DB.
    2) Builds a context string with build_context_from_rows().
    3) Calls the local Ollama chat model via call_ollama_chat().
    4) Returns (answer, chunks) where chunks is a list of dicts with
       content, score, and chunk_idx for the frontend to display.
    """
    # 1) Retrieve candidate chunks
    rows = search_development(question, top_k=top_k)

    if not rows:
        # No context found – keep answer honest and return no chunks.
        return (
            "I couldn't find any relevant context in your development documents for that question.",
            [],
        )

    # rows: (rank, score, file_name, chunk_index, content_preview)

    # 2) Build context string for the LLM
    context = build_context_from_rows(rows)

    # 3) Build the prompt and call Ollama
    prompt = build_prompt(question, context)
    answer = call_ollama_chat(prompt)

    # 4) Convert rows into chunk dicts for the UI
    chunks: List[Dict[str, Any]] = []
    for rank, score, file_name, chunk_idx, content_preview in rows:
        chunks.append(
            {
                "content": f"{file_name} [chunk {chunk_idx}]: {content_preview}",
                "score": float(score),
                "chunk_idx": int(chunk_idx),
            }
        )

    return answer, chunks


# ---------------------------------------------------------
# Chat history helpers
# ---------------------------------------------------------


def ensure_session(session_id: Optional[str]) -> str:
    """
    If session_id is provided, make sure it exists.
    If not provided, create a new session and return its id.
    """
    if session_id is None:
        new_id = str(uuid.uuid4())
        conn = get_pg_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_history.sessions (session_id, started_at, title)
                    VALUES (%s, NOW(), %s)
                    """,
                    (new_id, None),
                )
            conn.commit()
        finally:
            conn.close()
        return new_id

    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM chat_history.sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    """
                    INSERT INTO chat_history.sessions (session_id, started_at, title)
                    VALUES (%s, NOW(), %s)
                    """,
                    (session_id, None),
                )
                conn.commit()
    finally:
        conn.close()

    return session_id


def save_message(session_id: str, role: str, content: str) -> None:
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_history.messages (session_id, role, content, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (session_id, role, content),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------
# FastAPI app & CORS
# ---------------------------------------------------------

app = FastAPI(title="pgvector-rag (file_searcher)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Pydantic models – chat
# ---------------------------------------------------------


class ChunkModel(BaseModel):
    content: str
    score: float
    chunk_idx: int


class ChatRequestModel(BaseModel):
    question: str
    session_id: Optional[str] = None
    top_k: int = 5  # how many chunks to display in UI


class ChatResponseModel(BaseModel):
    answer: str
    chunks: List[ChunkModel]
    session_id: str


class SessionSummaryModel(BaseModel):
    session_id: str
    started_at: str
    title: Optional[str] = None


# ---------------------------------------------------------
# Pydantic models – SQL sandbox
# ---------------------------------------------------------


class SqlRequestModel(BaseModel):
    query: str


class SqlResponseModel(BaseModel):
    columns: List[str]
    rows: List[List[Any]]


# ---------------------------------------------------------
# Pydantic models – Library watcher
# ---------------------------------------------------------


class LibraryFileModel(BaseModel):
    file_path: str
    file_name: str
    ext: str
    size_bytes: int
    modified_ts: str
    status: str  # "new" | "ingested"


class IngestRequestModel(BaseModel):
    file_path: str


# ---------------------------------------------------------
# Library DB helpers
# ---------------------------------------------------------


def ensure_ingested_files_table() -> None:
    """
    Create library.ingested_files if it doesn't exist.
    Tracks which files have been ingested at least once.
    """
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS library;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS library.ingested_files (
                    file_path TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_ext TEXT NOT NULL,
                    first_ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
        conn.commit()
    finally:
        conn.close()


def scan_library_dir() -> List[Path]:
    """
    List all .pdf / .txt files under LIBRARY_DIR (recursive).
    """
    root = DEFAULT_LIBRARY_DIR
    if not root.exists():
        return []

    files: List[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in (".pdf", ".txt"):
            files.append(p)
    return files


# ---------------------------------------------------------
# Endpoints – Chat + Sessions
# ---------------------------------------------------------


@app.post("/api/chat", response_model=ChatResponseModel)
def chat(req: ChatRequestModel):
    """
    Main chat endpoint: RAG over your dev file_searcher DB.
    Uses search_development + qa_development helpers.
    """
    session_id = ensure_session(req.session_id)
    answer, chunks = run_rag_chat(req.question, top_k=req.top_k)
    save_message(session_id, "user", req.question)
    save_message(session_id, "assistant", answer)

    return ChatResponseModel(
        answer=answer,
        chunks=chunks,
        session_id=session_id,
    )


@app.get("/api/sessions", response_model=List[SessionSummaryModel])
def list_sessions(limit: int = 20):
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
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
    finally:
        conn.close()

    return [
        SessionSummaryModel(
            session_id=str(session_id),
            started_at=started_at.isoformat(),
            title=title,
        )
        for (session_id, started_at, title) in rows
    ]


@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    """
    Returns all messages for a given session (for the sidebar).
    """
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content, created_at
                FROM chat_history.messages
                WHERE session_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            )
            msg_rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "role": role,
            "content": content,
            "created_at": created_at.isoformat() if created_at else None,
        }
        for (role, content, created_at) in msg_rows
    ]


# ---------------------------------------------------------
# Endpoints – SQL helper for ToolsDrawer
# ---------------------------------------------------------


@app.post("/api/tools/sql", response_model=SqlResponseModel)
def run_sql_tool(req: SqlRequestModel):
    """
    Very simple SQL helper for the Tools drawer.
    WARNING: No sandboxing/permissions – trusted use only.
    """
    conn = get_pg_connection()
    try:
        cur = conn.cursor()
        cur.execute(req.query)

        if cur.description is not None:
            rows = cur.fetchall()
            columns = [col.name for col in cur.description]
        else:
            rows = []
            columns = []

        return SqlResponseModel(columns=columns, rows=rows)
    except psycopg2.Error as e:
        raise HTTPException(status_code=400, detail=f"SQL error: {e.pgerror or str(e)}")
    finally:
        conn.close()


@app.get("/api/tools/schemas", response_model=List[str])
def list_schemas() -> List[str]:
    """
    Helper endpoint – returns all non-system schemas in the database.
    Handy for the "List Schemas" button in ToolsDrawer.
    """
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('information_schema', 'pg_catalog')
                ORDER BY schema_name
                """
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


@app.get("/api/tools/tables", response_model=List[str])
def list_tables() -> List[str]:
    """
    Helper endpoint – returns all tables in all non-system schemas.
    Handy for the "List Tables" button in ToolsDrawer.
    """
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_schema || '.' || table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY table_schema, table_name
                """
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------
# Helper to run file_searcher CLI modules
# ---------------------------------------------------------


def _run_file_searcher_module(module_name: str, extra_args: Optional[List[str]] = None):
    """
    Helper: run a file_searcher module via:

        python -m file_searcher.<module_name> [extra_args...]

    in the FILE_SEARCHER_SRC directory.
    """
    if extra_args is None:
        extra_args = []

    if not FILE_SEARCHER_SRC.exists():
        raise HTTPException(
            status_code=500,
            detail=f"FILE_SEARCHER_SRC does not exist: {FILE_SEARCHER_SRC}",
        )

    cmd = [
        sys.executable,
        "-m",
        f"file_searcher.{module_name}",
        *extra_args,
    ]

    result = subprocess.run(
        cmd,
        cwd=str(FILE_SEARCHER_SRC),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=(
                f"{module_name} failed (code={result.returncode}):\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            ),
        )


# ---------------------------------------------------------
# Endpoints – Library watcher + ingest
# ---------------------------------------------------------


@app.get("/api/library/files", response_model=List[LibraryFileModel])
def list_library_files():
    """
    Scan LIBRARY_DIR for .pdf/.txt and join with library.ingested_files
    to show status: "new" vs "ingested".
    """
    ensure_ingested_files_table()

    files = scan_library_dir()
    # Build a quick lookup of ingested file paths
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT file_path
                FROM library.ingested_files
                """
            )
            ingested_paths = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

    out: List[LibraryFileModel] = []
    for p in files:
        st = p.stat()
        status = "ingested" if p.as_posix() in ingested_paths else "new"
        out.append(
            LibraryFileModel(
                file_path=p.as_posix(),
                file_name=p.name,
                ext=p.suffix.lower(),
                size_bytes=st.st_size,
                modified_ts=datetime.fromtimestamp(st.st_mtime).isoformat(),
                status=status,
            )
        )

    # Sort: new first, then by name
    out.sort(key=lambda f: (0 if f.status == "new" else 1, f.file_name.lower()))
    return out


@app.post("/api/library/ingest", response_model=LibraryFileModel)
def ingest_library_file(req: IngestRequestModel):
    """
    Ingest a single file (PDF/TXT) from LIBRARY_DIR and run the full DAG:

      1) file_searcher.ingest_file_to_development <file_path>
      2) file_searcher.embed_development_chunks <file_path>
      3) (optional) file_searcher.search_development CLI to refresh mart tables

    Also records the file in library.ingested_files so we don't re-ingest.
    """
    ensure_ingested_files_table()

    root = DEFAULT_LIBRARY_DIR.resolve()
    target = Path(req.file_path).resolve()

    # Safety: must live under LIBRARY_DIR
    if root != target and root not in target.parents:
        raise HTTPException(
            status_code=400,
            detail=f"File must be inside LIBRARY_DIR ({root}); got {target}",
        )

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    if target.suffix.lower() not in (".pdf", ".txt"):
        raise HTTPException(
            status_code=400,
            detail="Only .pdf and .txt files can be ingested",
        )

    file_path_str = target.as_posix()

    # Check if already ingested
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT first_ingested_at
                FROM library.ingested_files
                WHERE file_path = %s
                """,
                (file_path_str,),
            )
            row = cur.fetchone()
            already_ingested = row is not None
    finally:
        conn.close()

    st = target.stat()

    if already_ingested:
        # Don't re-run ingest; just return status
        return LibraryFileModel(
            file_path=file_path_str,
            file_name=target.name,
            ext=target.suffix.lower(),
            size_bytes=st.st_size,
            modified_ts=datetime.fromtimestamp(st.st_mtime).isoformat(),
            status="ingested",
        )

    # --- DAG starts here ---

    # 1) Ingest raw text → dev tables
    _run_file_searcher_module("ingest_file_to_development", [file_path_str])

    # 2) Create / update embeddings for dev chunks for this file
    _run_file_searcher_module("embed_development_chunks", [file_path_str])

    # 3) (Optional) Refresh any mart tables that depend on int.chunk_embeddings_development
    # If your CLI search_development script populates mart.search_chunks_development, you can call it here:
    # _run_file_searcher_module("search_development")

    # 4) Record as ingested (idempotent)
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO library.ingested_files (file_path, file_name, file_ext, first_ingested_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (file_path) DO NOTHING
                """,
                (file_path_str, target.name, target.suffix.lower()),
            )
        conn.commit()
    finally:
        conn.close()

    return LibraryFileModel(
        file_path=file_path_str,
        file_name=target.name,
        ext=target.suffix.lower(),
        size_bytes=st.st_size,
        modified_ts=datetime.fromtimestamp(st.st_mtime).isoformat(),
        status="ingested",
    )


# ---------------------------------------------------------
# Simple health check
# ---------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}
