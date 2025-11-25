-- echo: file_searcher db schema v0.1.1 2025-11-24
--
-- Location:
--   db/db_schema.sql
--
-- High-level design:
--   - WAP pattern schemas: raw, stg, int, mart
--   - Logical mapping:
--       raw  -> Bronze (original docs)
--       stg  -> Bronze→Silver transition (cleaned text)
--       int  -> Silver (chunks + embeddings)
--       mart -> Gold (search-optimized surfaces)
--
--   - Environments modeled with table suffixes:
--       *_staging, *_development, *_production
--
-- Sections:
--   1) Extensions
--   2) Schemas (raw/stg/int/mart)
--   3) RAW documents tables (Bronze)
--   4) STG text tables (cleaned text)
--   5) INT chunks + embeddings (Silver)
--   6) MART search surfaces (Gold)


-- =========================================================
-- 1) Extensions
-- =========================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;


-- =========================================================
-- 2) Schemas: WAP (raw, stg, int, mart)
-- =========================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS int;
CREATE SCHEMA IF NOT EXISTS mart;

COMMENT ON SCHEMA raw  IS 'raw (Bronze) zone – original ingested documents';
COMMENT ON SCHEMA stg  IS 'stg (Bronze→Silver) zone – cleaned/normalized intermediates';
COMMENT ON SCHEMA int  IS 'int (Silver) zone – chunked text + embeddings';
COMMENT ON SCHEMA mart IS 'mart (Gold) zone – query-optimized search surfaces';


-- =========================================================
-- 3) RAW documents tables (Bronze / raw)
-- =========================================================
--
-- Purpose:
--   Store original document metadata and optional raw bytes.
--   Different environments are modeled as separate tables.
--
-- Tables:
--   raw.documents_staging
--   raw.documents_development
--   raw.documents_production
--

CREATE TABLE IF NOT EXISTS raw.documents_staging (
    doc_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_path   TEXT,
    file_name     TEXT NOT NULL,
    mime_type     TEXT,
    payload_raw   BYTEA,                 -- optional: original bytes
    collected_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.documents_development (
    LIKE raw.documents_staging INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS raw.documents_production (
    LIKE raw.documents_staging INCLUDING ALL
);


-- =========================================================
-- 4) STG text tables (cleaned / normalized)
-- =========================================================
--
-- Purpose:
--   Store extracted and normalized text per document.
--   One row per doc_id, per environment.
--
-- Tables:
--   stg.document_text_staging
--   stg.document_text_development
--   stg.document_text_production
--

CREATE TABLE IF NOT EXISTS stg.document_text_staging (
    doc_id          UUID PRIMARY KEY,
    text_content    TEXT NOT NULL,
    normalized_text TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stg.document_text_development (
    LIKE stg.document_text_staging INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS stg.document_text_production (
    LIKE stg.document_text_staging INCLUDING ALL
);


-- =========================================================
-- 5) INT chunks + embeddings (Silver / int)
-- =========================================================
--
-- Purpose:
--   Store chunked text and embeddings per environment.
--
--   - int.chunks_* tables: text chunks + char offsets
--   - int.chunk_embeddings_* tables: pgvector embeddings
--
-- NOTE: Adjust vector(768) if your Ollama embedder uses a
--       different dimension.
--

-- ---------- 5.1 Chunks tables ---------------------------------
--
-- Purpose:
--   Store text chunks (no embeddings) per environment.
--   FK constraints are added in idempotent DO blocks below.
--

CREATE TABLE IF NOT EXISTS int.chunks_staging (
    chunk_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    doc_id       UUID NOT NULL,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    start_char   INTEGER,
    end_char     INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chunks_staging_doc
        FOREIGN KEY (doc_id) REFERENCES raw.documents_staging (doc_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS int.chunks_development (
    LIKE int.chunks_staging INCLUDING ALL
    EXCLUDING CONSTRAINTS
);

CREATE TABLE IF NOT EXISTS int.chunks_production (
    LIKE int.chunks_staging INCLUDING ALL
    EXCLUDING CONSTRAINTS
);


-- ---------- 5.1.1 Idempotent FK constraints for chunks --------
--
-- These DO blocks make the FK adds safe to run repeatedly.
--

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_chunks_development_doc'
    ) THEN
        ALTER TABLE int.chunks_development
            ADD CONSTRAINT fk_chunks_development_doc
                FOREIGN KEY (doc_id)
                REFERENCES raw.documents_development (doc_id)
                ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_chunks_production_doc'
    ) THEN
        ALTER TABLE int.chunks_production
            ADD CONSTRAINT fk_chunks_production_doc
                FOREIGN KEY (doc_id)
                REFERENCES raw.documents_production (doc_id)
                ON DELETE CASCADE;
    END IF;
END $$;



-- ---------- 5.2 Embeddings tables -----------------------------
--
-- Purpose:
--   pgvector embeddings per chunk, per environment.
--   FK constraints added via idempotent DO blocks.
--

CREATE TABLE IF NOT EXISTS int.chunk_embeddings_staging (
    chunk_id   UUID PRIMARY KEY,
    embedding  vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_chunk_embeddings_staging_chunk
        FOREIGN KEY (chunk_id) REFERENCES int.chunks_staging (chunk_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS int.chunk_embeddings_development (
    LIKE int.chunk_embeddings_staging INCLUDING ALL
    EXCLUDING CONSTRAINTS
);

CREATE TABLE IF NOT EXISTS int.chunk_embeddings_production (
    LIKE int.chunk_embeddings_staging INCLUDING ALL
    EXCLUDING CONSTRAINTS
);


-- ---------- 5.2.1 Idempotent FK constraints for embeddings ----

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_chunk_embeddings_development_chunk'
    ) THEN
        ALTER TABLE int.chunk_embeddings_development
            ADD CONSTRAINT fk_chunk_embeddings_development_chunk
                FOREIGN KEY (chunk_id)
                REFERENCES int.chunks_development (chunk_id)
                ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_chunk_embeddings_production_chunk'
    ) THEN
        ALTER TABLE int.chunk_embeddings_production
            ADD CONSTRAINT fk_chunk_embeddings_production_chunk
                FOREIGN KEY (chunk_id)
                REFERENCES int.chunks_production (chunk_id)
                ON DELETE CASCADE;
    END IF;
END $$;



-- =========================================================
-- 6) MART search surfaces (Gold / mart)
-- =========================================================
--
-- Purpose:
--   Store search-ready chunks for each environment, possibly
--   backed by views/materialized views in the future.
--
-- Tables:
--   mart.search_chunks_staging
--   mart.search_chunks_development
--   mart.search_chunks_production
--

CREATE TABLE IF NOT EXISTS mart.search_chunks_staging (
    chunk_id       UUID PRIMARY KEY,
    doc_id         UUID NOT NULL,
    chunk_index    INTEGER NOT NULL,
    content        TEXT NOT NULL,
    similarity_tag TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mart.search_chunks_development (
    LIKE mart.search_chunks_staging INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS mart.search_chunks_production (
    LIKE mart.search_chunks_staging INCLUDING ALL
);

-- =========================================================
-- 7) Indexes (pgvector + common access paths)
-- =========================================================
--
-- NOTE:
--   CREATE INDEX IF NOT EXISTS is idempotent.
--

-- Vector index for development embeddings (L2 distance)
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_dev_embedding
    ON int.chunk_embeddings_development
    USING ivfflat (embedding vector_l2_ops)
    WITH (lists = 100);

-- Helpful index on chunks_development by doc_id + chunk_index
CREATE INDEX IF NOT EXISTS idx_chunks_dev_docid_chunkindex
    ON int.chunks_development (doc_id, chunk_index);
