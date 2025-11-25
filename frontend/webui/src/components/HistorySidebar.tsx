// src/components/HistorySidebar.tsx
// echo: HistorySidebar.tsx v0.2.0 2025-11-18

import React from 'react'

export type SessionSummary = {
  session_id: string
  started_at: string
  title?: string | null
}

type Props = {
  sessions: SessionSummary[]
  loading: boolean
  error: string | null
  selectedSessionId: string | null
  onRefresh: () => void
  onOpenSession: (session_id: string) => void
}

export const HistorySidebar: React.FC<Props> = ({
  sessions,
  loading,
  error,
  selectedSessionId,
  onRefresh,
  onOpenSession,
}) => {
  return (
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
          onClick={onRefresh}
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
        {loading && (
          <div style={{ color: '#9ca3af', marginBottom: 8 }}>Loading sessions…</div>
        )}

        {error && (
          <div style={{ color: '#f97373', marginBottom: 8 }}>
            {error}
          </div>
        )}

        {!loading && !error && sessions.length === 0 && (
          <div style={{ color: '#6b7280' }}>No sessions yet.</div>
        )}

        {sessions.map(s => (
          <button
            key={s.session_id}
            type="button"
            onClick={() => onOpenSession(s.session_id)}
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
  )
}
