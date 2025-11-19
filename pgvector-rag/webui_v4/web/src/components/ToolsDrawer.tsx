// src/components/ToolsDrawer.tsx
// echo: ToolsDrawer.tsx v0.3.0 2025-11-18

import React, { useState } from 'react'

type SqlResult = {
  columns: string[]
  rows: any[][]
} | null

type ChunkInfo = {
  content: string
  score: number
  chunk_idx: number
}

type ChunkViewResponse = {
  chunks: ChunkInfo[]
}

type RerankChunk = {
  content: string
  base_score: number
  rerank_score: number
  chunk_idx: number
}

type RerankResponse = {
  chunks: RerankChunk[]
}

type EmbeddingResponse = {
  dimension: number
  norm: number
  vector: number[]
}

export const ToolsDrawer: React.FC = () => {
  // SQL helper
  const [sqlQuery, setSqlQuery] = useState(
    "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') ORDER BY 1,2 LIMIT 5"
  )
  const [sqlLoading, setSqlLoading] = useState(false)
  const [sqlError, setSqlError] = useState<string | null>(null)
  const [sqlResult, setSqlResult] = useState<SqlResult>(null)

  // Chunk viewer / reranker
  const [toolQuestion, setToolQuestion] = useState(
    'What is data engineering according to the book?'
  )
  const [toolTopK, setToolTopK] = useState(5)
  const [chunks, setChunks] = useState<ChunkInfo[]>([])
  const [rerankChunks, setRerankChunks] = useState<RerankChunk[]>([])
  const [chunksLoading, setChunksLoading] = useState(false)
  const [chunksError, setChunksError] = useState<string | null>(null)
  const [showRerank, setShowRerank] = useState(false)

  // Embedding inspector
  const [embedText, setEmbedText] = useState(
    'What is data engineering according to the book?'
  )
  const [embedLoading, setEmbedLoading] = useState(false)
  const [embedError, setEmbedError] = useState<string | null>(null)
  const [embedResult, setEmbedResult] = useState<EmbeddingResponse | null>(null)

  // ---------------------------------
  // SQL helper
  // ---------------------------------
  const runSql = async () => {
    setSqlLoading(true)
    setSqlError(null)
    setSqlResult(null)

    try {
      const res = await fetch('/api/tools/sql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: sqlQuery }),
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`SQL error (${res.status}): ${text}`)
      }

      const data = (await res.json()) as { columns: string[]; rows: any[][] }
      setSqlResult(data)
    } catch (err: any) {
      console.error('SQL helper error:', err)
      setSqlError(err.message || 'Failed to run query')
    } finally {
      setSqlLoading(false)
    }
  }

  // ---------------------------------
  // Chunk viewer
  // ---------------------------------
  const runChunkView = async () => {
    const q = toolQuestion.trim()
    if (!q) return

    setChunksLoading(true)
    setChunksError(null)
    setChunks([])
    setRerankChunks([])

    try {
      const res = await fetch('/api/tools/chunks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, top_k: toolTopK }),
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Chunk view error (${res.status}): ${text}`)
      }

      const data: ChunkViewResponse = await res.json()
      setChunks(data.chunks)
    } catch (err: any) {
      console.error('Chunk view error:', err)
      setChunksError(err.message || 'Failed to load chunks')
    } finally {
      setChunksLoading(false)
    }
  }

  const runRerank = async () => {
    const q = toolQuestion.trim()
    if (!q) return

    setChunksLoading(true)
    setChunksError(null)
    setChunks([])
    setRerankChunks([])

    try {
      const res = await fetch('/api/tools/chunks_rerank', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, top_k: toolTopK }),
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Rerank error (${res.status}): ${text}`)
      }

      const data: RerankResponse = await res.json()
      setRerankChunks(data.chunks)
    } catch (err: any) {
      console.error('Rerank error:', err)
      setChunksError(err.message || 'Failed to rerank chunks')
    } finally {
      setChunksLoading(false)
    }
  }

  // ---------------------------------
  // Embedding inspector
  // ---------------------------------
  const runEmbedding = async () => {
    const t = embedText.trim()
    if (!t) return

    setEmbedLoading(true)
    setEmbedError(null)
    setEmbedResult(null)

    try {
      const res = await fetch('/api/tools/embedding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: t }),
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Embedding error (${res.status}): ${text}`)
      }

      const data: EmbeddingResponse = await res.json()
      setEmbedResult(data)
    } catch (err: any) {
      console.error('Embedding error:', err)
      setEmbedError(err.message || 'Failed to compute embedding')
    } finally {
      setEmbedLoading(false)
    }
  }

  return (
    <aside
      style={{
        width: 360,
        borderLeft: '1px solid #1f2937',
        display: 'flex',
        flexDirection: 'column',
        background: '#020617',
      }}
    >
      <div
        style={{
          padding: '10px 12px',
          borderBottom: '1px solid #1f2937',
          fontSize: 13,
          fontWeight: 600,
        }}
      >
        Tools
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 10,
          fontSize: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
      >
        {/* SQL helper */}
        <section
          style={{
            borderRadius: 8,
            border: '1px solid #1f2937',
            padding: 8,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              marginBottom: 4,
            }}
          >
            SQL helper
          </div>
          <textarea
            value={sqlQuery}
            onChange={e => setSqlQuery(e.target.value)}
            rows={4}
            style={{
              width: '100%',
              resize: 'vertical',
              borderRadius: 6,
              border: '1px solid #374151',
              background: '#020617',
              color: '#e5e7eb',
              padding: 6,
              fontFamily: 'monospace',
              fontSize: 11,
            }}
          />
          <button
            type="button"
            onClick={runSql}
            disabled={sqlLoading}
            style={{
              marginTop: 6,
              padding: '4px 10px',
              borderRadius: 999,
              border: 'none',
              fontSize: 12,
              background: sqlLoading ? '#4b5563' : '#22c55e',
              color: '#020617',
              cursor: sqlLoading ? 'default' : 'pointer',
            }}
          >
            {sqlLoading ? 'Running…' : 'Run'}
          </button>
          {sqlError && (
            <div style={{ marginTop: 4, color: '#f97373' }}>{sqlError}</div>
          )}
          {sqlResult && sqlResult.rows.length > 0 && (
            <div
              style={{
                marginTop: 6,
                maxHeight: 160,
                overflow: 'auto',
                borderRadius: 6,
                border: '1px solid #1f2937',
              }}
            >
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: 11,
                }}
              >
                <thead>
                  <tr>
                    {sqlResult.columns.map(col => (
                      <th
                        key={col}
                        style={{
                          borderBottom: '1px solid #1f2937',
                          padding: '4px 6px',
                          textAlign: 'left',
                          background: '#030712',
                        }}
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sqlResult.rows.map((row, idx) => (
                    <tr key={idx}>
                      {row.map((cell, j) => (
                        <td
                          key={j}
                          style={{
                            borderBottom: '1px solid #111827',
                            padding: '4px 6px',
                          }}
                        >
                          {String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Chunk viewer + reranker */}
        <section
          style={{
            borderRadius: 8,
            border: '1px solid #1f2937',
            padding: 8,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              marginBottom: 4,
            }}
          >
            Retrieval / rerank debug
          </div>
          <textarea
            value={toolQuestion}
            onChange={e => setToolQuestion(e.target.value)}
            rows={3}
            style={{
              width: '100%',
              resize: 'vertical',
              borderRadius: 6,
              border: '1px solid #374151',
              background: '#020617',
              color: '#e5e7eb',
              padding: 6,
              fontFamily: 'system-ui',
              fontSize: 11,
            }}
          />
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              marginTop: 6,
            }}
          >
            <label style={{ fontSize: 11, color: '#9ca3af' }}>
              top_k:{' '}
              <input
                type="number"
                value={toolTopK}
                onChange={e =>
                  setToolTopK(Math.max(1, Number(e.target.value) || 1))
                }
                style={{
                  width: 50,
                  padding: '2px 4px',
                  borderRadius: 6,
                  border: '1px solid #374151',
                  background: '#020617',
                  color: '#e5e7eb',
                  fontSize: 11,
                }}
              />
            </label>
            <button
              type="button"
              onClick={runChunkView}
              disabled={chunksLoading}
              style={{
                padding: '4px 8px',
                borderRadius: 999,
                border: 'none',
                fontSize: 11,
                background: '#0ea5e9',
                color: '#020617',
                cursor: chunksLoading ? 'default' : 'pointer',
              }}
            >
              Raw chunks
            </button>
            <button
              type="button"
              onClick={runRerank}
              disabled={chunksLoading}
              style={{
                padding: '4px 8px',
                borderRadius: 999,
                border: 'none',
                fontSize: 11,
                background: '#a855f7',
                color: '#020617',
                cursor: chunksLoading ? 'default' : 'pointer',
              }}
            >
              Rerank
            </button>
            <label style={{ fontSize: 11, color: '#9ca3af', marginLeft: 'auto' }}>
              <input
                type="checkbox"
                checked={showRerank}
                onChange={e => setShowRerank(e.target.checked)}
                style={{ marginRight: 4 }}
              />
              Rerank debug
            </label>
          </div>
          {chunksLoading && (
            <div style={{ marginTop: 4, color: '#9ca3af' }}>Loading…</div>
          )}
          {chunksError && (
            <div style={{ marginTop: 4, color: '#f97373' }}>{chunksError}</div>
          )}
          {!chunksLoading && !chunksError && (chunks.length > 0 || rerankChunks.length > 0) && (
            <div
              style={{
                marginTop: 6,
                maxHeight: 180,
                overflow: 'auto',
                borderRadius: 6,
                border: '1px solid #1f2937',
                padding: 6,
                fontSize: 11,
                background: '#020617',
              }}
            >
              {showRerank && rerankChunks.length > 0
                ? rerankChunks.map((c, idx) => (
                    <div
                      key={idx}
                      style={{
                        marginBottom: 8,
                        borderBottom: '1px solid #111827',
                        paddingBottom: 6,
                      }}
                    >
                      <div
                        style={{
                          fontFamily: 'monospace',
                          fontSize: 10,
                          color: '#9ca3af',
                          marginBottom: 2,
                        }}
                      >
                        idx={c.chunk_idx} base={c.base_score.toFixed(3)} rerank=
                        {c.rerank_score.toFixed(3)}
                      </div>
                      <div>{c.content}</div>
                    </div>
                  ))
                : chunks.map((c, idx) => (
                    <div
                      key={idx}
                      style={{
                        marginBottom: 8,
                        borderBottom: '1px solid #111827',
                        paddingBottom: 6,
                      }}
                    >
                      <div
                        style={{
                          fontFamily: 'monospace',
                          fontSize: 10,
                          color: '#9ca3af',
                          marginBottom: 2,
                        }}
                      >
                        idx={c.chunk_idx} score={c.score.toFixed(3)}
                      </div>
                      <div>{c.content}</div>
                    </div>
                  ))}
            </div>
          )}
        </section>

        {/* Embedding inspector */}
        <section
          style={{
            borderRadius: 8,
            border: '1px solid #1f2937',
            padding: 8,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              marginBottom: 4,
            }}
          >
            Embedding inspector
          </div>
          <textarea
            value={embedText}
            onChange={e => setEmbedText(e.target.value)}
            rows={3}
            style={{
              width: '100%',
              resize: 'vertical',
              borderRadius: 6,
              border: '1px solid #374151',
              background: '#020617',
              color: '#e5e7eb',
              padding: 6,
              fontFamily: 'system-ui',
              fontSize: 11,
            }}
          />
          <button
            type="button"
            onClick={runEmbedding}
            disabled={embedLoading}
            style={{
              marginTop: 6,
              padding: '4px 10px',
              borderRadius: 999,
              border: 'none',
              fontSize: 12,
              background: embedLoading ? '#4b5563' : '#22c55e',
              color: '#020617',
              cursor: embedLoading ? 'default' : 'pointer',
            }}
          >
            {embedLoading ? 'Computing…' : 'Compute embedding'}
          </button>
          {embedError && (
            <div style={{ marginTop: 4, color: '#f97373' }}>{embedError}</div>
          )}
          {embedResult && (
            <div
              style={{
                marginTop: 6,
                fontSize: 11,
                color: '#e5e7eb',
              }}
            >
              <div>dim: {embedResult.dimension}</div>
              <div>norm: {embedResult.norm.toFixed(6)}</div>
              <div style={{ marginTop: 4 }}>
                <div style={{ color: '#9ca3af', marginBottom: 2 }}>
                  first 10 dims:
                </div>
                <code style={{ fontSize: 10 }}>
                  {embedResult.vector.slice(0, 10).map(v => v.toFixed(3)).join(', ')}
                </code>
              </div>
            </div>
          )}
        </section>
      </div>
    </aside>
  )
}
