// src/types/chat.ts
// echo: chat types v0.1.0 2025-11-17

export type Role = 'user' | 'assistant';

export interface Message {
  role: Role;
  content: string;
}

export interface Chunk {
  content: string;
  score: number;
  chunk_idx: number;
}

export interface ChatResponse {
  answer: string;
  chunks: Chunk[];
  session_id: string;
}

export interface SessionSummary {
  session_id: string;
  started_at: string;
  title?: string | null;
}

export interface HistoryMessage {
  role: Role;
  content: string;
  created_at?: string;
}

export interface SqlResult {
  rows: unknown[][];
  columns: string[];
}

export interface EmbeddingInspectorResult {
  dimension: number;
  norm: number;
  vector: number[];
}

export interface BookOption {
  id: string;
  label: string;
  sourceName: string;
}
