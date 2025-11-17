// src/App.tsx
// echo: App.tsx v0.1.0 2025-11-17

import React, { useState } from 'react'

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
}

const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
        body: JSON.stringify({ question }),
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Request failed (${res.status}): ${text}`)
      }

      const data: ChatResponse = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.answer }])
    } catch (err: any) {
      console.error(err)
      setError(err.message || 'Something went wrong')
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
          maxWidth: 900,
          height: '85vh',
          background: '#020617',
          borderRadius: 16,
          border: '1px solid #1f2937',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 50px -12px rgba(0,0,0,0.75)',
        }}
      >
        <header
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #1f2937',
          }}
        >
          <h1 style={{ fontSize: 20, margin: 0 }}>📚 FDE Book RAG – WebUI v3</h1>
          <p style={{ fontSize: 12, marginTop: 4, color: '#9ca3af' }}>
            Ask questions about <em>Fundamentals of Data Engineering</em>. Answers are grounded in your local
            pgvector + Ollama pipeline.
          </p>
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
            <div style={{ fontSize: 13, color: '#9ca3af', marginTop: 4 }}>Thinking with Gemma3:4b…</div>
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
  )
}

export default App
