// src/App.tsx
// echo: App.tsx v0.4.0 2025-11-18

import React, { useEffect, useState } from 'react'
import { HistorySidebar } from './components/HistorySidebar'
import type { SessionSummary as HistorySessionSummary } from './components/HistorySidebar'
import { ToolsDrawer } from './components/ToolsDrawer'
import { LibraryPanel } from './components/LibraryPanel'


type Message = {
  role: 'user' | 'assistant'
  content: string
}

type HistoryMessage = {
  role: 'user' | 'assistant'
  content: string
  created_at?: string
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


const App: React.FC = () => {
  // ----- History sidebar -----
  const [sessions, setSessions] = useState<HistorySessionSummary[]>([])
  const [loadingSessions, setLoadingSessions] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)

  // ----- Chat state -----
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const [lastContext, setLastContext] = useState<Chunk[] | null>(null)

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
      const data: HistorySessionSummary[] = await res.json()
      setSessions(data)
    } catch (err: any) {
      console.error('Error loading sessions:', err)
      setHistoryError(err.message || 'Failed to load history')
    } finally {
      setLoadingSessions(false)
    }
  }

  useEffect(() => {
    fetchSessions().catch(() => {
      // handled above
    })
  }, [])

  // -----------------------------
  // History: open a specific session
  // -----------------------------
  const handleOpenSession = async (targetSessionId: string) => {
    setSelectedSessionId(targetSessionId)
    setChatError(null)
    setChatLoading(true)

    try {
      const res = await fetch(`/api/sessions/${targetSessionId}/messages`)
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
      setSessionId(targetSessionId)
    } catch (err: any) {
      console.error('Error loading session messages:', err)
      setChatError(err.message || 'Failed to load session messages')
    } finally {
      setChatLoading(false)
    }
  }

  // -----------------------------
  // New chat: reset local state
  // -----------------------------
  const handleNewChat = () => {
    setSessionId(null)
    setSelectedSessionId(null)
    setMessages([])
    setInput('')
    setChatError(null)
  }

  // -----------------------------
  // Chat: send question to backend
  // -----------------------------
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const question = input.trim()
    if (!question || chatLoading) return

    setChatError(null)
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: question }])
    setChatLoading(true)

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
      setLastContext(Array.isArray(data.chunks) ? data.chunks : null)

      // Refresh sidebar so the new/updated session shows up
      fetchSessions().catch(() => {})
    } catch (err: any) {
      console.error('Chat error:', err)
      setChatError(err.message || 'Something went wrong')
    } finally {
      setChatLoading(false)
    }
  }

  const loadSession = async (id: string) => {
  const res = await fetch(`/api/session/${id}`);
  const data = await res.json();

  setMessages(data.messages);
  setLastContext([]); // reset until next /api/chat call
  }

  // -----------------------------
  // Render
  // -----------------------------
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
          maxWidth: 1400,
          height: '85vh',
          background: '#020617',
          borderRadius: 16,
          border: '1px solid #1f2937',
          display: 'flex',
          boxShadow: '0 25px 50px -12px rgba(0,0,0,0.75)',
          overflow: 'hidden',
        }}
      >
        {/* LEFT: History sidebar */}
        <HistorySidebar
          sessions={sessions}
          loading={loadingSessions}
          error={historyError}
          selectedSessionId={selectedSessionId}
          onRefresh={fetchSessions}
          onOpenSession={handleOpenSession}
        />

        {/* MIDDLE: Chat shell */}
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
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <h1 style={{ fontSize: 20, margin: 0 }}>📚 Book RAG – WebUI v4</h1>
              <p style={{ fontSize: 12, marginTop: 4, color: '#9ca3af' }}>
                Ask questions about your ingested books. Answers are grounded in your local
                pgvector + Ollama pipeline.
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
          </header>

          <main
            style={{
              flex: 1,
              padding: 12,
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              overflowY: 'auto',
              fontSize: 14,
            }}
          >
            {messages.length === 0 && (
              <div style={{ color: '#9ca3af' }}>
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

            {chatLoading && (
              <div style={{ fontSize: 13, color: '#9ca3af' }}>Thinking…</div>
            )}

            {chatError && (
              <div style={{ fontSize: 12, color: '#f97373' }}>{chatError}</div>
            )}
            {lastContext && (
              <div
                style={{
                  marginTop: '8px',
                  borderTop: '1px solid #e5e7eb',
                  paddingTop: '8px',
                  fontSize: '0.8rem',
                }}
              >
                <div
                  style={{
                    fontWeight: 500,
                    marginBottom: '4px',
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <span>Context chunks (RAG)</span>
                  <span style={{ color: '#6b7280' }}>
                    {lastContext.length > 0
                      ? `showing ${lastContext.length} chunks`
                      : 'no chunks returned'}
                  </span>
                </div>

                {lastContext.length === 0 ? (
                  <div
                    style={{
                      fontSize: '0.8rem',
                      color: '#6b7280',
                    }}
                  >
                    No context chunks were returned for this question.
                  </div>
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px',
                      maxHeight: '180px',
                      overflow: 'auto',
                    }}
                  >
                    {lastContext.map((chunk, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '6px 8px',
                          borderRadius: '6px',
                          background: '#f9fafb',
                          border: '1px solid #e5e7eb',
                        }}
                      >
                        <div
                          style={{
                            marginBottom: '2px',
                            fontSize: '0.75rem',
                            color: '#4b5563',
                            display: 'flex',
                            justifyContent: 'space-between',
                          }}
                        >
                          <span>Chunk #{chunk.chunk_idx}</span>
                          <span>score {chunk.score.toFixed(3)}</span>
                        </div>
                        <div
                          style={{
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          }}
                        >
                          {chunk.content}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            {sessionId && (
              <div
                style={{
                  marginTop: 'auto',
                  fontSize: 11,
                  color: '#4b5563',
                  textAlign: 'right',
                  fontFamily: 'monospace',
                }}
              >
                Session: {sessionId}
              </div>
            )}
          </main>
          <LibraryPanel />
          {/* Chat input */}
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
              disabled={chatLoading || !input.trim()}
              style={{
                padding: '8px 14px',
                borderRadius: 999,
                border: 'none',
                fontSize: 14,
                background: chatLoading ? '#4b5563' : '#22c55e',
                color: '#020617',
                cursor: chatLoading ? 'default' : 'pointer',
              }}
            >
              {chatLoading ? 'Sending…' : 'Send'}
            </button>
          </form>
        </div>

        {/* RIGHT: Tools drawer */}
        <ToolsDrawer />
      </div>
    </div>
  )
}

export default App
