// src/components/FileSearchPanel.tsx
// echo: FileSearchPanel.tsx v0.1.0 2025-11-24

import React, { useState } from 'react'

type SearchResult = {
  rank: number
  score: number
  file_name: string
  chunk_index: number
  content: string
}

type QaContextChunk = {
  id: number
  orig_rank: number
  orig_score: number
  file_name: string
  chunk_index: number
  snippet: string
}

type QaResponse = {
  answer: string
  context: QaContextChunk[]
}

export const FileSearchPanel: React.FC = () => {
  const [mode, setMode] = useState<'qa' | 'search'>('qa')
  const [input, setInput] = useState(
    'What is an operating system according to the book?'
  )
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [qaResponse, setQaResponse] = useState<QaResponse | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || isLoading) return

    setIsLoading(true)
    setError(null)
    setSearchResults([])
    setQaResponse(null)

    try {
      if (mode === 'search') {
        const res = await fetch('/file-search/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: text, top_k: 5 }),
        })

        if (!res.ok) {
          const t = await res.text()
          throw new Error(`Search error (${res.status}): ${t}`)
        }

        const json = await res.json()
        setSearchResults(json.results ?? [])
      } else {
        const res = await fetch('/file-search/qa', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: text,
            use_rerank: true,
            top_k_final: 5,
            top_n_candidates: 20,
          }),
        })

        if (!res.ok) {
          const t = await res.text()
          throw new Error(`QA error (${res.status}): ${t}`)
        }

        const json = (await res.json()) as QaResponse
        setQaResponse(json)
      }
    } catch (err: any) {
      console.error('FileSearchPanel error:', err)
      setError(err.message ?? 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }

  return (
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
        File searcher (library RAG)
      </div>

      {/* Mode toggle */}
      <div
        style={{
          display: 'flex',
          gap: 6,
          marginBottom: 6,
          fontSize: 11,
        }}
      >
        <button
          type="button"
          onClick={() => setMode('qa')}
          disabled={mode === 'qa'}
          style={{
            flex: 1,
            padding: '4px 6px',
            borderRadius: 999,
            border: '1px solid #374151',
            background: mode === 'qa' ? '#22c55e' : '#020617',
            color: mode === 'qa' ? '#020617' : '#e5e7eb',
            cursor: mode === 'qa' ? 'default' : 'pointer',
            fontSize: 11,
          }}
        >
          Q&A
        </button>
        <button
          type="button"
          onClick={() => setMode('search')}
          disabled={mode === 'search'}
          style={{
            flex: 1,
            padding: '4px 6px',
            borderRadius: 999,
            border: '1px solid #374151',
            background: mode === 'search' ? '#0ea5e9' : '#020617',
            color: mode === 'search' ? '#020617' : '#e5e7eb',
            cursor: mode === 'search' ? 'default' : 'pointer',
            fontSize: 11,
          }}
        >
          Raw search
        </button>
      </div>

      {/* Input + submit */}
      <form onSubmit={handleSubmit} style={{ marginBottom: 6 }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          rows={3}
          placeholder={
            mode === 'qa'
              ? 'Ask a question about your ingested books…'
              : 'Enter a semantic search query…'
          }
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
          type="submit"
          disabled={isLoading || !input.trim()}
          style={{
            marginTop: 6,
            padding: '4px 10px',
            borderRadius: 999,
            border: 'none',
            fontSize: 12,
            background: isLoading ? '#4b5563' : '#22c55e',
            color: '#020617',
            cursor: isLoading ? 'default' : 'pointer',
          }}
        >
          {isLoading
            ? 'Running…'
            : mode === 'qa'
            ? 'Ask'
            : 'Search'}
        </button>
      </form>

      {error && (
        <div style={{ marginBottom: 6, color: '#f97373', fontSize: 11 }}>
          {error}
        </div>
      )}

      {/* Results */}
      <div
        style={{
          maxHeight: 220,
          overflow: 'auto',
          borderRadius: 6,
          border: '1px solid #1f2937',
          padding: 6,
          fontSize: 11,
          background: '#020617',
        }}
      >
        {mode === 'search' && searchResults.length === 0 && !isLoading && !error && (
          <div style={{ color: '#6b7280' }}>No results yet.</div>
        )}
        {mode === 'qa' && !qaResponse && !isLoading && !error && (
          <div style={{ color: '#6b7280' }}>No answer yet.</div>
        )}

        {mode === 'search' &&
          searchResults.map(r => (
            <div
              key={`${r.file_name}-${r.chunk_index}-${r.rank}`}
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
                #{r.rank} score={r.score.toFixed(3)} file={r.file_name} chunk=
                {r.chunk_index}
              </div>
              <div>
                {r.content.length > 350
                  ? r.content.slice(0, 350) + '…'
                  : r.content}
              </div>
            </div>
          ))}

        {mode === 'qa' && qaResponse && (
          <div>
            <div
              style={{
                marginBottom: 8,
                borderBottom: '1px solid #111827',
                paddingBottom: 6,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  marginBottom: 4,
                }}
              >
                Answer
              </div>
              <div>{qaResponse.answer}</div>
            </div>

            {qaResponse.context.length > 0 && (
              <div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    marginBottom: 4,
                  }}
                >
                  Context chunks
                </div>
                {qaResponse.context.map(c => (
                  <div
                    key={`${c.file_name}-${c.chunk_index}-${c.id}`}
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
                      [{c.id}] rank={c.orig_rank} score={c.orig_score.toFixed(3)} file=
                      {c.file_name} chunk={c.chunk_index}
                    </div>
                    <div>{c.snippet}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
