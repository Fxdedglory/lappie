# Lappie – Full Local RAG System (PostgreSQL + pgvector + Ollama + React/TS)

## Overview
Lappie is a fully local Retrieval-Augmented Generation (RAG) system built from scratch using:

- **Python backend** (FastAPI)
- **PostgreSQL 16 + pgvector**
- **Ollama** (local embedding + chat models)
- **React + TypeScript** web UI
- **File ingestion pipeline** (`file_searcher` modules)
- **Library watcher + ingestion DAG**
- **Multi-session chat history**
- **Real RAG context display**
- **Full end‑to‑end ingestion → chunking → embeddings → mart → RAG search**

This project is designed to be **100% local**, fully transparent, modular, and easy to extend.

---

# 🧱 Architecture

```
E:\lappie│
├── pgvector-rag
│   ├── backend
│   │   ├── api               <-- FastAPI RAG/chat server
│   │   └── file_searcher     <-- ingestion + chunking + embeddings + search
│   └── web                   <-- React/TypeScript chat UI
│
└── Library                   <-- Your PDFs / text files for ingestion
```

---

# 🔥 RAG Data Flow (Full DAG)

```
 PDF/TXT
   │
   ▼
file_searcher.extract_text
   │
   ▼
raw.documents_development
   │
   ▼
file_searcher.chunker
   │
   ▼
stg.document_text_development
   │
   ▼
file_searcher.ingest_file_to_development
   │
   ▼
int.chunks_development
   │
   ▼
file_searcher.embeddings (Ollama)
   │
   ▼
int.chunk_embeddings_development
   │
   ▼
file_searcher.search_development
   │
   ▼
mart.search_chunks_development
   │
   ▼
FastAPI: /api/chat → run_rag_chat()
   │
   ▼
Ollama chat model
   │
   ▼
React UI + context chunks display
```

---

# 🗂 Components

## 1. **Backend API (`backend/api/`)**
FastAPI server that provides:
- `/api/chat` → main RAG chat endpoint  
- `/api/sessions` → list chat sessions  
- `/api/sessions/{id}/messages` → load history  
- `/api/library/files` → show Library folder status  
- `/api/library/ingest` → run full ingestion DAG  
- `/api/tools/sql` → SQL sandbox  
- `/api/tools/schemas` + `/api/tools/tables`  

### Key file:
- **`api_main.py`** – all endpoints, session handling, PG connection, RAG pipeline.

---

## 2. **File Searcher Pipeline (`backend/file_searcher/`)**

This directory contains the entire text‑processing pipeline:

| File | Purpose |
|------|---------|
| `extract_text.py` | Extract PDF/TXT into clean text |
| `chunker.py` | Convert raw text into windowed chunks |
| `ingest_file_to_development.py` | Run extract → chunk → stage → raw tables |
| `embed_development_chunks.py` | Use Ollama embedding model to embed chunks |
| `search_development.py` | Construct searchable mart tables |
| `qa_development_rerank.py` | RAG with reranker (CLI) |
| `qa_development.py` | RAG without reranker |
| `reranker.py` | Local reranking implementation |

### Database schemas created:
```
raw.documents_development
stg.document_text_development
int.chunks_development
int.chunk_embeddings_development
mart.search_chunks_development
```

---

## 3. **Web UI (`web/`)**
React/TypeScript app with:
- Chat interface
- Sidebar session list
- Message history loader
- RAG context panel
- Tools drawer (SQL runner)

Files of interest:
- `App.tsx`
- `components/SidebarSessions.tsx`
- `components/ContextChunks.tsx`
- `hooks/useChat.ts`

---

# 📦 Environment Setup

## 1. Conda Environment
```
conda create -n pgvectorscale-rag python=3.11
conda activate pgvectorscale-rag
pip install -r requirements.txt
```

### Required Python dependencies:
- fastapi
- uvicorn
- psycopg2-binary
- python-dotenv
- pdfminer.six
- requests
- tenacity
- pydantic

---

## 2. PostgreSQL + pgvector
Ensure DB is created:
```
CREATE DATABASE file_searcher;
CREATE EXTENSION vector;
```

Your `.env` handles:
```
PGHOST=localhost
PGPORT=5433
PGDATABASE=file_searcher
PGUSER=postgres
PGPASSWORD=postgres
```

---

## 3. Ollama
Start service:
```
ollama serve
ollama pull nomic-embed-text
ollama pull gemma3:4b
```

---

## 4. Run Backend API
```
cd backend/api
uvicorn api_main:app --reload --host 0.0.0.0 --port 8000
```

---

## 5. Run Frontend
```
cd web
npm install
npm run dev
```

---

# 📚 Library Folder

Drop files here:
```
E:\lappie\Library```

The system automatically:
- Detects new PDFs/TXTs  
- Shows them in `/api/library/files`  
- Ingests them via `/api/library/ingest`  
- Prevents re-ingestion  

---

# 🧪 Sample Queries

```
What is an operating system?
Explain multi-level indexing.
Define write-ahead logging.
Summarize chapter 1.
```

RAG context appears under the message in the UI.

---

# 🛠 Useful Manual Commands

### Rebuild embeddings for a single file
```
python -m file_searcher.embed_development_chunks "E:/lappie/Library/foo.pdf"
```

### Run CLI RAG (rerank)
```
python -m file_searcher.qa_development_rerank "What is concurrency?"
```

---

# 📌 Future Upgrades

- Add user-defined metadata to docs  
- Add PDF page image viewer + snippet highlighter  
- Add multi-file merged search  
- Add embeddings monitoring dashboard  
- Add ingestion stats in the UI  

---

# 🏁 Project Status: **Fully Functional**
Everything from ingestion → embeddings → search → chat is working correctly.

Ready for GitHub push + documentation expansion.

