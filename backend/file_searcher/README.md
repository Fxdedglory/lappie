````markdown
<!-- README_backend_file_searcher.md -->
# Backend – `file_searcher` (WAP / pgvector RAG stack)

**Echo:** `file_searcher README v0.2.0 – 2025-11-25`

This package is the **data side** of your pgvector RAG system:

- Defines the **Postgres schemas & tables** (raw → stg → int → mart, plus chat history).
- Provides **CLI scripts** to:
  - Initialize the database.
  - Ingest PDF/TXT files into the **development** environment.
  - Extract and chunk text.
  - Generate pgvector **embeddings** via Ollama.
  - Build the **search mart** table.
  - Run **QA / RAG** queries for development.

The REST API in `backend/api` imports and shells into these modules to power the Web UI and library ingest.

---

## 1. Directory layout

```text
backend/
  file_searcher/
    db/
      db_schema.sql          # WAP schemas/tables (raw, stg, int, mart)
      chat_history.sql       # chat_history.sessions + chat_history.messages

    src/
      .env                   # env vars used by file_searcher modules
      file_searcher/
        __init__.py
        init_db.py
        extract_text.py
        ingest_text.py
        ingest_file_to_development.py
        chunker.py
        embeddings.py
        embed_development_chunks.py
        search_development.py
        qa_development.py
        qa_development_rerank.py
        reranker.py
        multi_ingest_development.py

    tests/
      ... (optional / future)
````

---

## 2. Database design (WAP + chat history)

### 2.1 WAP schemas (raw/stg/int/mart)

The main schema file `db/db_schema.sql` sets up a **Write–Audit–Publish** layout: 

* **Schemas**

  * `raw`  – Bronze: original ingested documents.
  * `stg`  – Bronze→Silver: cleaned / normalized text.
  * `int`  – Silver: chunks + embeddings.
  * `mart` – Gold: search-ready chunk table.

* **Environment suffixes**

  * `*_staging`
  * `*_development`
  * `*_production`

Current stack uses the **development** tables:

* `raw.documents_development` – original docs (per file).
* `stg.document_text_development` – normalized full text per doc.
* `int.chunks_development` – text chunks (with char offsets).
* `int.chunk_embeddings_development` – pgvector embeddings per chunk.
* `mart.search_chunks_development` – search-facing chunks (content + tags).

Vector extension and core indexes are also defined here (e.g. `vector(768)`, IVF index on embeddings). 

### 2.2 Chat history schema

The file `db/chat_history.sql` defines chat storage for the Web UI: 

* `chat_history.sessions`

  * `session_id UUID PRIMARY KEY`
  * `started_at TIMESTAMPTZ`
  * `title TEXT` (currently unused / nullable)
* `chat_history.messages`

  * `id BIGSERIAL PRIMARY KEY`
  * `session_id UUID` → FK → `chat_history.sessions`
  * `role TEXT` (`'user'` or `'assistant'`)
  * `content TEXT`
  * `created_at TIMESTAMPTZ`

The FastAPI backend (`api_main.py`) calls into this schema to persist conversations and populate the **Sessions sidebar**.

---

## 3. Environment & configuration

### 3.1 Conda environment

All scripts run under the **`pgvectorscale-rag`** environment:

Key Python deps (non-exhaustive):

* `psycopg2-binary`
* `requests`
* `python-dotenv`
* `numpy` / `typing-extensions` (indirect)
* Ollama running locally for embeddings / chat.

### 3.2 `.env` for file_searcher

`backend/file_searcher/src/.env` mirrors the API `.env` and is loaded by `init_db.py` and related modules:

```env
# Postgres
PGHOST=localhost
PGPORT=5433
PGDATABASE=file_searcher
PGUSER=postgres
PGPASSWORD=postgres

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=gemma3:4b
OLLAMA_API_KEY=ollama
```

> **Important:** This `.env` must live in `backend/file_searcher/src/.env` so the `load_config()` utility in `init_db.py` can find it.

---

## 4. CLI scripts & responsibilities

All commands assume:

```powershell
conda activate pgvectorscale-rag
cd E:\lappie\pgvector-rag\backend\file_searcher\src
```

and are run as **modules**:

```powershell
python -m file_searcher.<module_name> [args...]
```

### 4.1 `init_db.py`

**Purpose:** Bootstrap database schemas/tables and apply `db_schema.sql` + `chat_history.sql`.

Typical flow:

* Load `.env` → get PG connection.
* Apply `db/db_schema.sql` (WAP schemas/tables). 
* Apply `db/chat_history.sql` (chat history). 

You normally run this **once per environment** (or when you add new tables):

```powershell
python -m file_searcher.init_db
```

---

### 4.2 `extract_text.py`

**Purpose:** Extract reasonable-looking plain text from PDF/TXT inputs.

* Handles:

  * PDFs → text (likely via `pdfminer`/`pypdf` or similar).
  * TXT → normalized text.
* Produces text consumed by `ingest_text.py` / `ingest_file_to_development.py`.

---

### 4.3 `ingest_text.py`

**Purpose:** Take an already-available text blob and write into **development** tables.

* Target tables:

  * `raw.documents_development`
  * `stg.document_text_development`
* This is a utility module that is called by `ingest_file_to_development.py` once text has been extracted.

---

### 4.4 `chunker.py`

**Purpose:** Turn long text documents into overlapping **chunks** for RAG.

Typical responsibilities:

* Configurable `max_words` / `overlap_words`.
* Splits normalized text into segments with overlap to preserve context.
* Emits `Chunk` objects with:

  * `content`
  * `chunk_index`
  * optional `start_char` / `end_char`.

Used by `ingest_file_to_development.py` to write into `int.chunks_development`.

---

### 4.5 `ingest_file_to_development.py`

**Purpose:** One-shot **file ingest** for the development environment.

High-level DAG (per file):

1. Insert row into `raw.documents_development` with:

   * `source_path`, `file_name`, `mime_type`, etc.
2. Use `extract_text.py` to get clean text.
3. Write full text into `stg.document_text_development`.
4. Use `chunker.py` to produce chunks.
5. Write chunks into `int.chunks_development` (with `doc_id`, `chunk_index`, `content`, offsets).

CLI (current usage pattern):

```powershell
python -m file_searcher.ingest_file_to_development "E:/lappie/Library/SomeBook.pdf"
```

This is the same command your **Library Ingest API** uses in its DAG.

---

### 4.6 `embeddings.py`

**Purpose:** Wrap Ollama’s embedding endpoint behind a simple Python API.

* Reads `OLLAMA_BASE_URL` and `OLLAMA_EMBED_MODEL` from `.env`.

* Implements a batch function:

  ```python
  def embed_texts(texts: list[str]) -> list[list[float]]:
      ...
  ```

* Used by `embed_development_chunks.py` to generate vector embeddings for chunks.

---

### 4.7 `embed_development_chunks.py`

**Purpose:** Create pgvector **embeddings** for development chunks.

High-level steps:

1. Load config / connect to DB via `init_db.load_config()` / `get_connection()`.
2. Look in `int.chunks_development` for chunks that **don’t yet** have embeddings in `int.chunk_embeddings_development`.
3. Call `embeddings.embed_texts()` in reasonably sized batches.
4. Insert rows into `int.chunk_embeddings_development`:

   * `chunk_id`
   * `embedding vector(768)`
   * `created_at`

Example usage (per file, as you’ve used):

```powershell
python -m file_searcher.embed_development_chunks "E:/lappie/Library/Abraham-Silberschatz-Operating-System-Concepts-10th-2018.pdf"
python -m file_searcher.embed_development_chunks "E:/lappie/Library/Fundamentals-of-Data-Engineering.pdf"
```

The Library ingest API also has a flavor that runs **without args** to embed any remaining chunks.

---

### 4.8 `search_development.py`

**Purpose:** Build / refresh and query the **mart** search surface.

Responsibilities:

* **Refresh step** (called in your API DAG):

  * Populate or update `mart.search_chunks_development` from
    `int.chunks_development` + `int.chunk_embeddings_development`.
  * Ensure `mart.search_chunks_development` is in sync and queryable.

* **Search step** (imported directly by `api_main.run_rag_chat()`):

  * `search_development(question: str, top_k: int)` → list of rows:

    ```python
    (rank, score, file_name, chunk_index, preview_text)
    ```
  * Uses the vector index on `int.chunk_embeddings_development` and the mart table to return the best candidate chunks.

---

### 4.9 `qa_development.py`

**Purpose:** “Classic” RAG pipeline without rerank.

* Uses `search_development()` to get top-k chunks.
* Builds a **context string** via `build_context_from_rows()`.
* Constructs a final **LLM prompt** with `build_prompt(question, context)`.
* Calls `call_ollama_chat()` (chat model from `.env`).
* Returns an answer string (and optionally some context info).

This is what `api_main.run_rag_chat()` now uses directly for **Real RAG context** in the Web UI.

---

### 4.10 `reranker.py` & `qa_development_rerank.py`

**Purpose:** Add a **local reranker** model for improved ranking.

* `reranker.py`:

  * Wraps a cross-encoder / reranker model (e.g., via Ollama or another service).
  * Re-scores candidate chunks given a query.

* `qa_development_rerank.py`:

  * CLI you’ve been using:

    ```powershell
    python -m file_searcher.qa_development_rerank "What is an operating system?" --top-k-final 5 --top-n-candidates 30
    ```
  * Prints:

    * `=== ANSWER (with rerank) ===`
    * `=== CONTEXT (reranked top chunks) ===` with per-chunk snippet lines.

While the REST API **no longer shells out** to this script for live queries (it uses `qa_development` directly), it remains a **great CLI tool** for debugging and validating RAG quality.

---

### 4.11 `multi_ingest_development.py`

**Purpose:** Batch ingest a whole directory (e.g., the Library).

Likely responsibilities:

* Walk a directory tree.
* For each file:

  * Call `ingest_file_to_development.py`.
  * Optionally call `embed_development_chunks.py` as you go.

The Web API currently implements its own ingest DAG wire-up, but `multi_ingest_development.py` remains useful for **one-off batch jobs** on the command line.

---

## 5. End-to-end DAG (per book)

Putting it all together, your **per-book** DAG looks like this:

1. **DB init (one-time / occasional)**

   * `python -m file_searcher.init_db`
   * Creates schemas/tables: `raw`, `stg`, `int`, `mart`, `chat_history`.

2. **Ingest file → development**

   * `python -m file_searcher.ingest_file_to_development "E:/lappie/Library/<Book>.pdf"`
   * Writes into:

     * `raw.documents_development`
     * `stg.document_text_development`
     * `int.chunks_development`

3. **Embed chunks**

   * `python -m file_searcher.embed_development_chunks "E:/lappie/Library/<Book>.pdf"`
   * Writes into:

     * `int.chunk_embeddings_development`

4. **Build search mart**

   * `python -m file_searcher.search_development`
   * Refreshes:

     * `mart.search_chunks_development`

5. **Ask questions (CLI)**

   * `python -m file_searcher.qa_development_rerank "Your question..." --top-k-final 5 --top-n-candidates 30`
   * or use the **Web UI**, which:

     * Calls `search_development()` → `qa_development` via FastAPI.
     * Displays answer + context chunks in the right-hand panel.
     * Logs conversation to `chat_history.*`.

---

## 6. How API and Web UI use `file_searcher`

* **FastAPI backend (`backend/api/api_main.py`):**

  * Imports:

    * `search_development`, `build_context_from_rows`, `build_prompt`, `call_ollama_chat`.
  * Defines `run_rag_chat()` that:

    * Calls `search_development(question, top_k)`.
    * Builds context and prompt with `qa_development`.
    * Calls Ollama chat and returns:

      * `answer`
      * `chunks` (file name + chunk index + score + preview content).
  * Exposes these via `/api/chat`.

* **Library ingest endpoints:**

  * Use `ingest_file_to_development`, `embed_development_chunks`, and `search_development` as part of the `/api/library/ingest` DAG.
  * Store ingested file metadata in `library.ingested_files` (separate schema created at API layer).

The Web UI then:

* Calls `/api/library/files` and `/api/library/ingest` to manage books.
* Calls `/api/chat` for RAG chat, showing **real context chunks**.
* Calls `/api/tools/sql` to run ad-hoc SQL against all schemas.

---

## 7. Quick start checklist (file_searcher only)

1. **Create / update DB schemas**

   ```powershell
   conda activate pgvectorscale-rag
   cd E:\lappie\pgvector-rag\backend\file_searcher\src
   python -m file_searcher.init_db
   ```

2. **Ingest a PDF**

   ```powershell
   python -m file_searcher.ingest_file_to_development "E:/lappie/Library/Abraham-Silberschatz-Operating-System-Concepts-10th-2018.pdf"
   ```

3. **Embed chunks**

   ```powershell
   python -m file_searcher.embed_development_chunks "E:/lappie/Library/Abraham-Silberschatz-Operating-System-Concepts-10th-2018.pdf"
   ```

4. **Refresh mart**

   ```powershell
   python -m file_searcher.search_development
   ```

5. **CLI test**

   ```powershell
   python -m file_searcher.qa_development_rerank "What is an operating system?" --top-k-final 5 --top-n-candidates 30
   ```

At that point, the **API + Web UI** should show:

* Correct answers from OS Concepts and FDE.
* Real context chunks in the RAG pane.
* Ingested file status in `/api/library/files`.

---