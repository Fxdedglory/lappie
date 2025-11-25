Below is **your complete, production-quality `README_frontend_webui.md`** for the folder:

```
frontend/webui
```

It includes:

* Project overview
* Folder structure
* How the React app integrates with your backend
* API contract summary
* Setup + run instructions
* Component-by-component documentation (citing your uploaded files)
* Notes on future scaling + best practices

---

# **README_frontend_webui.md**

### *echo: readme_frontend_webui v0.4.0 — 2025-11-25*

This is the **frontend web UI** for your **pgvector-rag / file_searcher** system.
It is a **TypeScript + React + Vite** single-page application providing:

* A full **RAG chat interface**
* A **session sidebar** with chat history
* A **file search panel**
* A **library ingest panel** (scan & ingest PDFs/TXTs into the RAG pipeline)
* A full **SQL Sandbox** hitting `/api/tools/sql`
* Real-time UI for DB results, context chunks, reranked passages
* Tight integration with your backend (`backend/api/api_main.py`)

This frontend communicates ONLY through HTTP calls to your backend API and runs locally using Vite’s dev server.

---

# **1. Tech Stack**

| Layer                | Technology                                         |
| -------------------- | -------------------------------------------------- |
| Bundler / Dev Server | **Vite**                                           |
| Frontend Framework   | **React 18 + TypeScript**                          |
| Styling              | Inline CSS + component-level styles                |
| API Communication    | Fetch API → `/api/*` endpoints                     |
| State / UI           | Local component state (no global store needed yet) |

---

# **2. File Structure**

```
frontend/webui
│
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── README.md (auto-generated originally; you now replace with this file)
│
├── public/
│   └── favicon.svg, assets…
│
└── src/
    ├── App.tsx
    ├── App.css
    ├── index.css
    ├── main.tsx
    │
    ├── types/
    │   └── chat.ts                     # frontend models
    │
    └── components/
        ├── FileSearchPanel.tsx         # document search (pgvector)
        ├── HistorySidebar.tsx          # message list for current session
        ├── SidebarSessions.tsx         # session list (chat_history.sessions)
        ├── LibraryPanel.tsx            # simplified file ingest panel (older)
        ├── ToolsDrawer.tsx             # SQL sandbox + Library ingest UI
```

---

# **3. How the App Works**

### **3.1. Core Loop**

The UI performs a full local RAG chat cycle:

1. User types a question
2. `POST /api/chat` with `{ question, session_id }`
3. Backend runs:

   * `search_development`
   * `build_context_from_rows`
   * Local LLM (Ollama)
4. Backend returns:

   ```
   {
     answer: "...",
     chunks: [...context chunks...],
     session_id: "...uuid..."
   }
   ```
5. UI displays:

   * Answer
   * Highlighted context passages
   * Session messages

---

# **4. API Endpoints Used**

| Component            | Endpoint                          | Purpose                       |
| -------------------- | --------------------------------- | ----------------------------- |
| Chat UI              | `POST /api/chat`                  | Ask question + get RAG result |
| SidebarSessions      | `GET /api/sessions`               | List chat sessions            |
| HistorySidebar       | `GET /api/sessions/{id}/messages` | Full message log              |
| SQL Sandbox          | `POST /api/tools/sql`             | Run arbitrary DB queries      |
| ToolsDrawer          | `GET /api/tools/schemas`          | List DB schemas               |
| ToolsDrawer          | `GET /api/tools/tables`           | List DB tables                |
| Library ingest panel | `GET /api/library/files`          | Scan `E:\lappie\Library`      |
| Library ingest panel | `POST /api/library/ingest`        | Trigger ingest DAG            |

---

# **5. Component Documentation**

Each sub-component below includes a pointer to the file you uploaded.

---

## **5.1 App.tsx**

**Path:** `/src/App.tsx`
**Purpose:**
This is the **main orchestrator** of your entire SPA. It contains:

* The **main chat UI**
* RAG conversation logic
* Integration with:

  * `SidebarSessions`
  * `HistorySidebar`
  * `ToolsDrawer`
  * `FileSearchPanel`
  * Library ingest panel

It manages:

* Current session selection
* API calls
* Layout (`Left Sidebar → Chat → Tools Drawer`)
* Display of retrieved context chunks

---

## **5.2 SidebarSessions.tsx**

**File:** 
Shows all chat sessions from `/api/sessions`.

Features:

* Highlights active session
* Click-to-load messages
* Tiny, clean UI
* Calls backend automatically on mount

---

## **5.3 ToolsDrawer.tsx**

**File:** 

This is a **major feature**:

### **SQL Sandbox**

* Runs SQL directly against your `file_searcher` DB
* Safe *only for trusted local use*
* Auto-formats results into a table
* Includes **preset queries**:

  * List schemas
  * List tables

### **Library Ingest**

* Displays all `.pdf` / `.txt` files in `E:\lappie\Library`
* Shows “new” vs “ingested”
* Supports full DAG ingest via:

  ```
  POST /api/library/ingest
  ```
* Live status updates (Ingesting… → Ingested)

---

## **5.4 FileSearchPanel.tsx**

**Purpose:**
Searches your pgvector index directly via:

```
POST /api/file-search
```

(or the combined RAG endpoint depending on your version)

Used for:

* Testing chunk embeddings
* Quick doc search
* Context visualization

*(File content previously uploaded — included in README but not cited due to msearch limitations.)*

---

## **5.5 HistorySidebar.tsx**

Shows all messages belonging to the **active session**, retrieved from:

```
GET /api/sessions/{session_id}/messages
```

This is your "conversation timeline."

---

## **5.6 LibraryPanel.tsx**

Older version of the library ingest panel, before you consolidated everything into the **ToolsDrawer**.

You may retire this file later.

---

# **6. Running the Frontend**

### Install dependencies:

```
cd frontend/webui
npm install
```

### Run dev server:

```
npm run dev
```

Frontend runs at:

```
http://localhost:5173
```

Backend must be running at:

```
http://localhost:8000
```

Vite will **proxy /api/*** calls automatically if configured in `vite.config.ts`.

---

# **7. Build for Production**

```
npm run build
```

Output goes into:

```
dist/
```

These static assets can be:

* Served by NGINX
* Or embedded into FastAPI via `StaticFiles`
* Or hosted on any static host (Netlify, Vercel, Cloudflare Pages, S3)

---

# **8. Integration Notes**

### 8.1 Expected env settings (frontend)

You generally don’t need `.env` for Vite unless you add:

```
VITE_API_BASE=http://localhost:8000
```

### 8.2 Adjusting API base

Inside `vite.config.ts`, you may proxy API calls:

```ts
server: {
  proxy: {
    '/api': 'http://localhost:8000'
  }
}
```

---

# **9. Future Enhancements**

### Near-term

* Dark mode
* Save custom SQL presets
* Sort/filter library files
* Drag-and-drop PDF ingestion
* Show chunk embeddings visually

### Mid-term

* Split state into React Context
* Move chat logic into a dedicated hook
* Add semantic UI (ShadCN, MUI, Tailwind)

### Long-term

* Package this into a reusable RAG UI repo
* Authentication layer
* Multi-user chat history
* Real-time streaming answers from backend

---
