// src/components/LibraryPanel.tsx
// echo: LibraryPanel.tsx v0.1.0 2025-11-24

import React, { useEffect, useState } from 'react'

type LibraryFile = {
  file_path: string
  file_name: string
  ext: string
  size_bytes: number
  modified_ts: string
  status: string // "new" | "ingested" | etc.
}

export const LibraryPanel: React.FC = () => {
  const [files, setFiles] = useState<LibraryFile[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ingestingPath, setIngestingPath] = useState<string | null>(null)

  const loadFiles = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/library/files')
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const data: LibraryFile[] = await res.json()
      setFiles(data)
    } catch (e: any) {
      console.error('library load error', e)
      setError(e?.message ?? 'Failed to load library files')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadFiles()
  }, [])

  const ingestFile = async (filePath: string) => {
    setIngestingPath(filePath)
    setError(null)
    try {
      const res = await fetch('/api/library/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(`Ingest failed (${res.status}): ${text}`)
      }
      // On success, re-load list so status flips from "new" -> "ingested"
      await loadFiles()
    } catch (e: any) {
      console.error('ingest error', e)
      setError(e?.message ?? 'Ingest error')
    } finally {
      setIngestingPath(null)
    }
  }

  return (
    <section
      style={{
        marginTop: '16px',
        borderRadius: '8px',
        border: '1px solid #e5e7eb',
        background: '#f9fafb',
        padding: '10px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <div>
          <h2
            style={{
              fontSize: '0.95rem',
              fontWeight: 600,
              marginBottom: '2px',
            }}
          >
            Library watcher
          </h2>
          <p style={{ fontSize: '0.8rem', color: '#4b5563' }}>
            Scans <code>LIBRARY_DIR</code> for <code>.pdf</code> / <code>.txt</code>.
            Files marked as ingested are not re-ingested.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadFiles()}
          disabled={loading}
          style={{
            padding: '4px 10px',
            borderRadius: '999px',
            border: '1px solid #d1d5db',
            background: loading ? '#e5e7eb' : '#ffffff',
            fontSize: '0.75rem',
            cursor: loading ? 'default' : 'pointer',
          }}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && (
        <div
          style={{
            fontSize: '0.8rem',
            color: '#b91c1c',
            background: '#fee2e2',
            borderRadius: '6px',
            padding: '6px',
            whiteSpace: 'pre-wrap',
          }}
        >
          {error}
        </div>
      )}

      {files.length === 0 && !loading && !error && (
        <p style={{ fontSize: '0.8rem', color: '#6b7280' }}>
          No <code>.pdf</code> or <code>.txt</code> files found in your library directory.
        </p>
      )}

      {files.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.8rem',
            }}
          >
            <thead>
              <tr>
                <th
                  style={{
                    textAlign: 'left',
                    padding: '4px 6px',
                    borderBottom: '1px solid #e5e7eb',
                    background: '#f3f4f6',
                  }}
                >
                  File
                </th>
                <th
                  style={{
                    textAlign: 'left',
                    padding: '4px 6px',
                    borderBottom: '1px solid #e5e7eb',
                    background: '#f3f4f6',
                  }}
                >
                  Status
                </th>
                <th
                  style={{
                    textAlign: 'right',
                    padding: '4px 6px',
                    borderBottom: '1px solid #e5e7eb',
                    background: '#f3f4f6',
                  }}
                >
                  Size
                </th>
                <th
                  style={{
                    textAlign: 'left',
                    padding: '4px 6px',
                    borderBottom: '1px solid #e5e7eb',
                    background: '#f3f4f6',
                  }}
                >
                  Modified
                </th>
                <th
                  style={{
                    textAlign: 'center',
                    padding: '4px 6px',
                    borderBottom: '1px solid #e5e7eb',
                    background: '#f3f4f6',
                  }}
                >
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.file_path}>
                  <td
                    style={{
                      padding: '4px 6px',
                      borderBottom: '1px solid #f3f4f6',
                      maxWidth: '260px',
                      whiteSpace: 'nowrap',
                      textOverflow: 'ellipsis',
                      overflow: 'hidden',
                    }}
                    title={f.file_path}
                  >
                    {f.file_name}
                  </td>
                  <td
                    style={{
                      padding: '4px 6px',
                      borderBottom: '1px solid #f3f4f6',
                    }}
                  >
                    {f.status === 'ingested' ? (
                      <span style={{ color: '#10b981' }}>ingested</span>
                    ) : (
                      <span style={{ color: '#ea580c' }}>new</span>
                    )}
                  </td>
                  <td
                    style={{
                      padding: '4px 6px',
                      borderBottom: '1px solid #f3f4f6',
                      textAlign: 'right',
                    }}
                  >
                    {(f.size_bytes / (1024 * 1024)).toFixed(2)} MB
                  </td>
                  <td
                    style={{
                      padding: '4px 6px',
                      borderBottom: '1px solid #f3f4f6',
                    }}
                  >
                    {new Date(f.modified_ts).toLocaleString()}
                  </td>
                  <td
                    style={{
                      padding: '4px 6px',
                      borderBottom: '1px solid #f3f4f6',
                      textAlign: 'center',
                    }}
                  >
                    {f.status === 'ingested' ? (
                      <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>
                        Already ingested
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => void ingestFile(f.file_path)}
                        disabled={ingestingPath === f.file_path}
                        style={{
                          padding: '4px 10px',
                          borderRadius: '999px',
                          border: 'none',
                          fontSize: '0.75rem',
                          cursor:
                            ingestingPath === f.file_path ? 'default' : 'pointer',
                          background:
                            ingestingPath === f.file_path ? '#9ca3af' : '#2563eb',
                          color: '#ffffff',
                        }}
                      >
                        {ingestingPath === f.file_path ? 'Ingesting…' : 'Ingest'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
