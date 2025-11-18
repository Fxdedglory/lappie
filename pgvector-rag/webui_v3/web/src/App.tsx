// src/App.tsx
// echo: App.tsx v0.3.0 2025-11-17

import React, { useEffect, useState } from 'react'

type Message = {
  role: 'user' | 'assistant'
  content: string
}

type Chunk = {
  content: string
  score: number
  chunk_idx: number
}

type ChatResponse = {
  answer: string
  chunks: Chunk[]
  session_id: string
}

type SessionSummary = {
  session_id: string
  started_at: string
  title?: string | null
}

type HistoryMessage = {
  role: 'user' | 'assistant'
  content: string
  created_at?: string
}

const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)

  // History-related state
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [loadingSessions, setLoadingSessions] = useState(false)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)

  // -----------------------------
  // New chat: resets local state
  // -----------------------------
  const handleNewChat = () => {
    setMessages([])
    setSessionId(null)
    setError(null)
    setInput('')
    setSelectedSessionId(null)
  }

  // -----------------------------
  // Send question to backend
  // -----------------------------
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const question = input.trim()
    if (!question || loading) return

    setError(null)
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: question }])
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          session_id: sessionId ?? undefined,
        }),
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Request failed (${res.status}): ${text}`)
      }

      const data: ChatResponse = await res.json()
      setSessionId(data.session_id)
      setMessages(prev => [...prev, { role: 'assistant', content: data.answer }])
    } catch (err: any) {
      console.error(err)
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  // -----------------------------
  // History: fetch recent sessions
  // -----------------------------
  const fetchSessions = async () => {
    setLoadingSessions(true)
    setHistoryError(null)

    try {
      const res = await fetch('/api/sessions')
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Failed to load sessions (${res.status}): ${text}`)
      }
      const data: SessionSummary[] = await res.json()
      setSessions(data)
    } catch (err: any) {
      console.error(err)
      setHistoryError(err.message || 'Failed to load history')
    } finally {
      setLoadingSessions(false)
    }
  }

  useEffect(() => {
    // Load session list on first render
    fetchSessions().catch(() => {
      // errors already handled in fetchSessions
    })
  }, [])

  // -----------------------------
  // History: load a specific session
  // -----------------------------
  const handleOpenSession = async (session_id: string) => {
    setSelectedSessionId(session_id)
    setError(null)
    setLoading(true)

    try {
      const res = await fetch(`/api/sessions/${session_id}/messages`)
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Failed to load session messages (${res.status}): ${text}`)
      }

      const data: HistoryMessage[] = await res.json()

      const mapped: Message[] = data.map(m => ({
        role: m.role,
        content: m.content,
      }))

      setMessages(mapped)
      setSessionId(session_id)
    } catch (err: any) {
      console.error(err)
      setError(err.message || 'Failed to load session messages')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        height: '100vh',
        margin: 0,
        padding: 16,
        background: '#020617',
        color: '#e5e7eb',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 1100,
          height: '85vh',
          background: '#020617',
          borderRadius: 16,
          border: '1px solid #1f2937',
          display: 'flex',
          boxShadow: '0 25px 50px -12px rgba(0,0,0,0.75)',
          overflow: 'hidden',
        }}
      >
        {/* Left: History Sidebar */}
        <aside
          style={{
            width: 260,
            borderRight: '1px solid #1f2937',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              padding: '10px 12px',
              borderBottom: '1px solid #1f2937',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 600 }}>History</div>
            <button
              type="button"
              onClick={fetchSessions}
              style={{
                fontSize: 11,
                padding: '4px 8px',
                borderRadius: 999,
                border: '1px solid #374151',
                background: '#020617',
                color: '#e5e7eb',
                cursor: 'pointer',
              }}
            >
              Refresh
            </button>
          </div>

          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: 8,
              fontSize: 12,
            }}
          >
            {loadingSessions && (
              <div style={{ color: '#9ca3af', marginBottom: 8 }}>Loading sessions…</div>
            )}

            {historyError && (
              <div style={{ color: '#f97373', marginBottom: 8 }}>
                {historyError}
              </div>
            )}

            {sessions.length === 0 && !loadingSessions && !historyError && (
              <div style={{ color: '#6b7280' }}>No sessions yet.</div>
            )}

            {sessions.map(s => (
              <button
                key={s.session_id}
                type="button"
                onClick={() => handleOpenSession(s.session_id)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  background:
                    selectedSessionId === s.session_id ? '#111827' : 'transparent',
                  borderRadius: 8,
                  border: 'none',
                  padding: '6px 8px',
                  marginBottom: 4,
                  cursor: 'pointer',
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 500,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {s.title || 'Untitled chat'}
                </div>
                <div
                  style={{
                    fontSize: 10,
                    color: '#6b7280',
                    marginTop: 2,
                  }}
                >
                  {new Date(s.started_at).toLocaleString()}
                </div>
              </button>
            ))}
          </div>
        </aside>

        {/* Right: Chat Panel */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <header
            style={{
              padding: '12px 16px',
              borderBottom: '1px solid #1f2937',
              display: 'flex',
              flexDirection: 'column',
              gap: 4,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <h1 style={{ fontSize: 20, margin: 0 }}>📚 FDE Book RAG – WebUI v3</h1>
                <p style={{ fontSize: 12, marginTop: 4, color: '#9ca3af' }}>
                  Ask questions about <em>Fundamentals of Data Engineering</em>. Answers are
                  grounded in your local pgvector + Ollama pipeline.
                </p>
              </div>
              <button
                type="button"
                onClick={handleNewChat}
                style={{
                  fontSize: 12,
                  padding: '6px 10px',
                  borderRadius: 999,
                  border: '1px solid #374151',
                  background: '#020617',
                  color: '#e5e7eb',
                  cursor: 'pointer',
                }}
              >
                + New chat
              </button>
            </div>

            {sessionId && (
              <div style={{ fontSize: 10, color: '#6b7280' }}>
                Session:{' '}
                <span style={{ fontFamily: 'monospace' }}>{sessionId}</span>
              </div>
            )}
          </header>

          <main
            style={{
              flex: 1,
              padding: 12,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
            }}
          >
            {messages.length === 0 && (
              <div style={{ fontSize: 14, color: '#9ca3af' }}>
                <p>Try asking:</p>
                <ul style={{ paddingLeft: 18 }}>
                  <li>“What is data engineering according to the book?”</li>
                  <li>“How does the book describe the ingestion phase?”</li>
                  <li>“What are the main components of a modern data platform?”</li>
                </ul>
              </div>
            )}

            {messages.map((m, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  background: m.role === 'user' ? '#1d4ed8' : '#111827',
                  color: '#e5e7eb',
                  padding: '8px 10px',
                  borderRadius: 12,
                  maxWidth: '80%',
                  whiteSpace: 'pre-wrap',
                  fontSize: 14,
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    opacity: 0.7,
                    marginBottom: 4,
                  }}
                >
                  {m.role === 'user' ? 'You' : 'Book Assistant'}
                </div>
                {m.content}
              </div>
            ))}

            {loading && (
              <div style={{ fontSize: 13, color: '#9ca3af', marginTop: 4 }}>
                Thinking with Gemma3:4b…
              </div>
            )}

            {error && (
              <div style={{ fontSize: 12, color: '#f97373', marginTop: 4 }}>
                {error}
              </div>
            )}
          </main>

          <form
            onSubmit={handleSubmit}
            style={{
              padding: 12,
              borderTop: '1px solid #1f2937',
              display: 'flex',
              gap: 8,
            }}
          >
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask something about the book..."
              style={{
                flex: 1,
                padding: '8px 10px',
                borderRadius: 999,
                border: '1px solid #374151',
                background: '#020617',
                color: '#e5e7eb',
                fontSize: 14,
                outline: 'none',
              }}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                padding: '8px 14px',
                borderRadius: 999,
                border: 'none',
                fontSize: 14,
                background: loading ? '#4b5563' : '#22c55e',
                color: '#020617',
                cursor: loading ? 'default' : 'pointer',
              }}
            >
              {loading ? 'Sending…' : 'Send'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default App
