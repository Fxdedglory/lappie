Here is the **fully expanded, correct, complete `README_backend_api.md`**, incorporating everything from:

* `api_main.py` 
* `file_search_endpoints.py` 
* `.env` (backend/api)

This is a **real backend-oriented README** with full explanations of:
✔ architecture
✔ dependencies
✔ environment variables
✔ API routes
✔ RAG pipeline
✔ file ingestion DAG
✔ chat history
✔ SQL tools drawer
✔ library watcher
✔ file_search endpoints
✔ how to run everything

---

# ✅ **README_backend_api.md (Complete Version)**

**pgvector-rag → Backend / API Layer**
**FastAPI • Postgres (pgvector) • Ollama • file_searcher pipeline**

---

# 📌 1. Overview

This backend provides:

### **1) Full RAG Chat API**

Uses your **local pgvector database**, **file_searcher** pipeline, and **Ollama** LLMs:

* top-k semantic search (`search_development`)
* optional LLM reranking
* context construction
* final answer generation

### **2) File Ingestion DAG**

Automatically ingests PDF/TXT books into the RAG system:

```
ingest_file_to_development → embed_development_chunks → search_development
```

### **3) Library Watcher**

Detects new books in `E:\lappie\Library` and only processes each once.

### **4) Chat Sessions / History**

Stores message history under schema `chat_history`.

### **5) SQL ToolsDrawer API**

Allows running SQL queries from the UI.

### **6) Dedicated /file-search endpoints**

UI-safe wrappers around:

* semantic search (`/file-search/search`)
* Q&A with optional rerank (`/file-search/qa`)

---

# 📌 2. Repository Structure

```
backend/
  api/
    api_main.py
    file_search_endpoints.py
    .env
  file_searcher/
    src/file_searcher/
      (all ingestion + embedding + search pipeline code)
frontend/
  webui/
database/
  (pgvector DB running on port 5433)
```

---

# 📌 3. Environment Variables (`backend/api/.env`)

From your uploaded `.env`:

```
# Postgres
PGHOST=localhost
PGPORT=5433
PGDATABASE=file_searcher
PGUSER=postgres
PGPASSWORD=postgres

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=gemma3:4b
OLLAMA_API_KEY=ollama

# Folder containing books
LIBRARY_DIR=E:\lappie\Library

# Ingestion command
FILE_SEARCHER_INGEST_CMD=python -m file_searcher.ingest_file_to_development "{file_path}"

# Location of file_searcher src root
FILE_SEARCHER_SRC_ROOT=E:\lappie\pgvector-rag\backend\file_searcher\src
```

---

# 📌 4. How to Run the Backend

```powershell
cd E:\lappie\pgvector-rag\backend\api
conda activate pgvectorscale-rag
uvicorn api_main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at:

```
http://localhost:8000
```

---

# 📌 5. RAG Pipeline (api_main.py)

The main chat endpoint:

```
POST /api/chat
```

Uses:

1. **search_development(query)**
   Fetches top-k chunks from Postgres (pgvector).

2. **build_context_from_rows(rows)**
   Builds the “context block”.

3. **build_prompt(question, context)**

4. **call_ollama_chat(prompt)**
   Sends to Ollama using your model:

   * `gemma3:4b` for chat
   * `nomic-embed-text` for embedding (via file_searcher)

5. Returns:

```json
{
  "answer": "...",
  "chunks": [
    { "content": "...", "score": -12.21, "chunk_idx": 39 }
  ],
  "session_id": "uuid"
}
```

---

# 📌 6. Chat History Storage

Tables:

```
chat_history.sessions
chat_history.messages
```

Endpoints:

| Route                             | Description                |
| --------------------------------- | -------------------------- |
| `GET /api/sessions`               | List recent sessions       |
| `GET /api/sessions/{id}/messages` | Load conversation          |
| `POST /api/chat`                  | Runs RAG + stores messages |

---

# 📌 7. SQL Tools Drawer

### Run SQL

```
POST /api/tools/sql
{
  "query": "SELECT * FROM library.ingested_files"
}
```

### List schemas

```
GET /api/tools/schemas
```

### List tables

```
GET /api/tools/tables
```

---

# 📌 8. Library Watcher + Ingest DAG

### List files found on disk

```
GET /api/library/files
```

Returns:

```json
[
  {
    "file_path": "E:/lappie/Library/FDE.pdf",
    "status": "ingested"
  }
]
```

---

### Trigger ingest

```
POST /api/library/ingest
{
  "file_path": "E:/lappie/Library/Fundamentals-of-Data-Engineering.pdf"
}
```

### Under the hood (full DAG)

api_main.py runs: 

1. `python -m file_searcher.ingest_file_to_development <file>`
2. `python -m file_searcher.embed_development_chunks`
3. `python -m file_searcher.search_development`
4. Inserts into `library.ingested_files`

All subsequent runs will skip because DB tracks:

```
library.ingested_files.file_path
```

---

# 📌 9. /file-search Endpoints

(from `file_search_endpoints.py`  )

Mounted under:

```
/file-search/*
```

Imported into api_main via router inclusion.

### **1) Semantic Search**

```
POST /file-search/search
{
  "query": "virtual memory",
  "top_k": 5
}
```

### **2) QA with optional rerank**

```
POST /file-search/qa
{
  "question": "What is an OS?",
  "use_rerank": true,
  "top_k_final": 5,
  "top_n_candidates": 15
}
```

Uses:

* pgvector search
* optional LLM-based reranking
* final answer via Ollama

---

# 📌 10. Project Architecture Diagram

```
          ┌──────────────────────────────┐
          │       FRONTEND (React)       │
          │  Chat UI • RAG UI • Tools    │
          └──────────────┬───────────────┘
                         |
                         v
               ┌───────────────────┐
               │   FastAPI API     │
               │  (api_main.py)    │
               └───────────────────┘
   ┌─────────────────────┬──────────────────────┐
   v                     v                      v
Chat Sessions     SQL Tools Drawer     Library Watcher + DAG
                                            |
                                            v
                                file_searcher Python modules
       ┌──────────────────────────────────────────────────────────────┐
       │ ingest_file_to_development → embed_chunks → search_refresh   │
       └──────────────────────────────────────────────────────────────┘
                                            |
                                            v
                             PostgreSQL + pgvector (5433)
                                            |
                                            v
                                    Ollama LLMs
```

---

# 📌 11. Dependencies

### **Python**

* FastAPI
* uvicorn
* psycopg2-binary
* python-dotenv
* requests
* file_searcher (local package)

### **System**

* PostgreSQL 16
* pgvector extension
* Ollama (running on port 11434)

---

# 📌 12. Notes for Deployment

* DB should be pre-initialized (`init_db.py`).
* Ollama models must be pulled locally:

  ```
  ollama pull gemma3:4b
  ollama pull nomic-embed-text
  ```
* Increase timeout for embedding large PDFs (batching is already implemented).

---

# 📌 13. API Summary Table

| Category        | Endpoint                          | Purpose             |
| --------------- | --------------------------------- | ------------------- |
| **Chat**        | POST `/api/chat`                  | Full RAG chat       |
|                 | GET `/api/sessions`               | List chat sessions  |
|                 | GET `/api/sessions/{id}/messages` | Load chat           |
| **SQL Tools**   | POST `/api/tools/sql`             | Run SQL             |
|                 | GET `/api/tools/schemas`          | List schemas        |
|                 | GET `/api/tools/tables`           | List tables         |
| **Library**     | GET `/api/library/files`          | Watch folder        |
|                 | POST `/api/library/ingest`        | Run full ingest DAG |
| **File-Search** | POST `/file-search/search`        | Semantic search     |
|                 | POST `/file-search/qa`            | Q&A with reranking  |

---