// src/components/ToolsDrawer.tsx
// echo: ToolsDrawer.tsx v0.5.0 2025-11-24

import React, { useState } from 'react'

type SqlResult = {
  columns: string[]
  rows: any[][]
} | null

type LibraryFile = {
  file_path: string
  file_name: string
  ext: string
  size_bytes: number
  modified_ts: string
  status: 'new' | 'ingested'
}


// Preset helper queries
const LIST_SCHEMAS_SQL = [
  '-- List schemas in current database',
  'SELECT schema_name',
  'FROM information_schema.schemata',
  'ORDER BY schema_name;'
].join('\n')

const LIST_TABLES_SQL = [
  '-- List tables (schemas + names)',
  'SELECT table_schema, table_name',
  'FROM information_schema.tables',
  "WHERE table_type = 'BASE TABLE'",
  'ORDER BY table_schema, table_name;'
].join('\n')

export const ToolsDrawer: React.FC = () => {
  const [sqlQuery, setSqlQuery] = useState(
    [
      '-- SQL sandbox (file_searcher DB)',
      '-- Example: inspect chunks table',
      "SELECT doc_id, chunk_index, LEFT(content, 120) AS preview",
      'FROM mart.search_chunks_development',
      'LIMIT 10;'
    ].join('\n')
  )
  const [result, setResult] = useState<SqlResult>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

    //library ingest state
  const [libraryFiles, setLibraryFiles] = useState<LibraryFile[]>([])
  const [libraryLoading, setLibraryLoading] = useState(false)
  const [libraryError, setLibraryError] = useState<string | null>(null)
  const [libraryBusyPath, setLibraryBusyPath] = useState<string | null>(null)

  const runSql = async () => {
    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/tools/sql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: sqlQuery }),
      })

      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }

      const data: SqlResult = await res.json()
      setResult(data)
    } catch (e: any) {
      console.error('SQL error', e)
      setError(e?.message ?? 'Unknown SQL error')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }
    const loadLibraryFiles = async () => {
    setLibraryLoading(true)
    setLibraryError(null)
    try {
      const res = await fetch('/api/library/files')
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const data: LibraryFile[] = await res.json()
      setLibraryFiles(data)
    } catch (e: any) {
      console.error('Library error', e)
      setLibraryError(e?.message ?? 'Unknown library error')
    } finally {
      setLibraryLoading(false)
    }
  }

  const ingestFile = async (filePath: string) => {
    setLibraryBusyPath(filePath)
    setLibraryError(null)
    try {
      const res = await fetch('/api/library/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: filePath }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      // Successfully ingested – reload list to update status
      await loadLibraryFiles()
    } catch (e: any) {
      console.error('Ingest error', e)
      setLibraryError(e?.message ?? 'Unknown ingest error')
    } finally {
      setLibraryBusyPath(null)
    }
  }

  return (
    <aside
      className="tools-drawer"
      style={{
        width: '380px',
        borderLeft: '1px solid #e2e8f0',
        background: '#f8fafc',
        display: 'flex',
        flexDirection: 'column',
        padding: '12px',
        gap: '12px',
      }}
    >
      <div>
        <h2
          style={{
            fontSize: '1.1rem',
            fontWeight: 600,
            marginBottom: '4px',
          }}
        >
          SQL Sandbox
        </h2>
        <p style={{ fontSize: '0.85rem', color: '#4b5563' }}>
          Runs against your <code>file_searcher</code> PostgreSQL database via{' '}
          <code>/api/tools/sql</code>.
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <label
          htmlFor="sql-input"
          style={{ fontSize: '0.8rem', fontWeight: 500, color: '#374151' }}
        >
          SQL query
        </label>

        {/* Preset buttons */}
        <div
          style={{
            display: 'flex',
            gap: '6px',
            marginBottom: '4px',
            flexWrap: 'wrap',
          }}
        >
          <button
            type="button"
            onClick={() => setSqlQuery(LIST_SCHEMAS_SQL)}
            style={{
              padding: '4px 8px',
              borderRadius: '999px',
              border: '1px solid #d1d5db',
              background: '#e5e7eb',
              fontSize: '0.75rem',
              cursor: 'pointer',
            }}
          >
            List schemas
          </button>
          <button
            type="button"
            onClick={() => setSqlQuery(LIST_TABLES_SQL)}
            style={{
              padding: '4px 8px',
              borderRadius: '999px',
              border: '1px solid #d1d5db',
              background: '#e5e7eb',
              fontSize: '0.75rem',
              cursor: 'pointer',
            }}
          >
            List tables
          </button>
        </div>

        <textarea
          id="sql-input"
          value={sqlQuery}
          onChange={(e) => setSqlQuery(e.target.value)}
          spellCheck={false}
          style={{
            width: '100%',
            minHeight: '140px',
            resize: 'vertical',
            fontFamily:
              'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            fontSize: '0.8rem',
            padding: '8px',
            borderRadius: '6px',
            border: '1px solid #d1d5db',
            background: '#ffffff',
          }}
        />
        <button
          onClick={runSql}
          disabled={loading}
          style={{
            alignSelf: 'flex-start',
            padding: '6px 12px',
            borderRadius: '6px',
            border: 'none',
            cursor: loading ? 'default' : 'pointer',
            fontSize: '0.85rem',
            fontWeight: 500,
            background: loading ? '#9ca3af' : '#2563eb',
            color: '#ffffff',
          }}
        >
          {loading ? 'Running…' : 'Run query'}
        </button>
      </div>

      {error && (
        <div
          style={{
            fontSize: '0.8rem',
            color: '#b91c1c',
            background: '#fee2e2',
            borderRadius: '6px',
            padding: '8px',
            whiteSpace: 'pre-wrap',
          }}
        >
          {error}
        </div>
      )}

      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: 'auto',
          borderRadius: '6px',
          border: '1px solid #e5e7eb',
          background: '#ffffff',
          padding: '8px',
        }}
      >
        <h3
          style={{
            fontSize: '0.9rem',
            fontWeight: 500,
            marginBottom: '6px',
          }}
        >
          Results
        </h3>

        {!result && !error && (
          <p style={{ fontSize: '0.8rem', color: '#6b7280' }}>
            Run a query to see results here.
          </p>
        )}

        {result && result.rows.length === 0 && (
          <p style={{ fontSize: '0.8rem', color: '#6b7280' }}>
            Query executed successfully, but returned no rows.
          </p>
        )}

        {result && result.rows.length > 0 && (
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
                  {result.columns.map((col) => (
                    <th
                      key={col}
                      style={{
                        textAlign: 'left',
                        padding: '4px 6px',
                        borderBottom: '1px solid #e5e7eb',
                        background: '#f9fafb',
                        fontWeight: 600,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, idx) => (
                  <tr key={idx}>
                    {row.map((cell, cIdx) => (
                      <td
                        key={cIdx}
                        style={{
                          padding: '4px 6px',
                          borderBottom: '1px solid #f3f4f6',
                          verticalAlign: 'top',
                          maxWidth: '320px',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {cell === null
                          ? 'NULL'
                          : typeof cell === 'object'
                          ? JSON.stringify(cell)
                          : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
            {/* Library ingest section */}
      <div
        style={{
          marginTop: '12px',
          borderRadius: '6px',
          border: '1px solid #e5e7eb',
          background: '#ffffff',
          padding: '8px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          maxHeight: '260px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '4px',
          }}
        >
          <h3
            style={{
              fontSize: '0.9rem',
              fontWeight: 500,
            }}
          >
            Library ingest
          </h3>
          <button
            type="button"
            onClick={loadLibraryFiles}
            disabled={libraryLoading}
            style={{
              padding: '4px 8px',
              borderRadius: '999px',
              border: '1px solid #d1d5db',
              background: libraryLoading ? '#e5e7eb' : '#f3f4f6',
              fontSize: '0.75rem',
              cursor: libraryLoading ? 'default' : 'pointer',
            }}
          >
            {libraryLoading ? 'Loading…' : 'Refresh'}
          </button>
        </div>

        <p style={{ fontSize: '0.75rem', color: '#6b7280' }}>
          Scans <code>E:\lappie\Library</code> for <code>.pdf</code>/<code>.txt</code> via
          <code> /api/library/files</code>. Click <em>Ingest</em> to run the full DAG.
        </p>

        {libraryError && (
          <div
            style={{
              fontSize: '0.75rem',
              color: '#b91c1c',
              background: '#fee2e2',
              borderRadius: '6px',
              padding: '6px',
              whiteSpace: 'pre-wrap',
            }}
          >
            {libraryError}
          </div>
        )}

        <div
          style={{
            marginTop: '4px',
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            borderTop: '1px solid #f3f4f6',
            paddingTop: '4px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          {libraryFiles.length === 0 && !libraryLoading && (
            <p style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
              No files yet. Click <strong>Refresh</strong> to scan your library.
            </p>
          )}

          {libraryFiles.map((f) => (
            <div
              key={f.file_path}
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
                padding: '4px 6px',
                borderRadius: '6px',
                border: '1px solid #e5e7eb',
                background:
                  f.status === 'new' ? '#ecfdf5' : '#f9fafb',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    maxWidth: '220px',
                  }}
                  title={f.file_name}
                >
                  {f.file_name}
                </div>
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 6px',
                    borderRadius: '999px',
                    border: '1px solid #d1d5db',
                    background:
                      f.status === 'new'
                        ? '#bbf7d0'
                        : '#e5e7eb',
                  }}
                >
                  {f.status}
                </span>
              </div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '0.7rem',
                  color: '#6b7280',
                  gap: '4px',
                }}
              >
                <span>
                  {(f.size_bytes / (1024 * 1024)).toFixed(1)} MB
                </span>
                <button
                  type="button"
                  disabled={
                    f.status === 'ingested' || libraryBusyPath === f.file_path
                  }
                  onClick={() => ingestFile(f.file_path)}
                  style={{
                    padding: '2px 8px',
                    borderRadius: '999px',
                    border: 'none',
                    fontSize: '0.7rem',
                    cursor:
                      f.status === 'ingested' || libraryBusyPath === f.file_path
                        ? 'default'
                        : 'pointer',
                    background:
                      f.status === 'ingested'
                        ? '#e5e7eb'
                        : '#22c55e',
                    color:
                      f.status === 'ingested'
                        ? '#4b5563'
                        : '#ffffff',
                  }}
                >
                  {f.status === 'ingested'
                    ? 'Ingested'
                    : libraryBusyPath === f.file_path
                    ? 'Ingesting…'
                    : 'Ingest'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}
