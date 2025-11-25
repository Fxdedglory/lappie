-- 1) Schema for chat history
CREATE SCHEMA IF NOT EXISTS chat_history;

-- 2) Sessions table
CREATE TABLE IF NOT EXISTS chat_history.sessions (
  session_id   UUID PRIMARY KEY,
  started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  title        TEXT
);

-- 3) Messages table
CREATE TABLE IF NOT EXISTS chat_history.messages (
  id          BIGSERIAL PRIMARY KEY,
  session_id  UUID NOT NULL REFERENCES chat_history.sessions(session_id) ON DELETE CASCADE,
  role        TEXT NOT NULL,         -- 'user' or 'assistant'
  content     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional quick sanity check
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'chat_history'
ORDER BY table_name;
