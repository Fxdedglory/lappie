// src/components/SidebarSessions.tsx
// echo: SidebarSessions.tsx v0.3.0 2025-11-24

import React, { useEffect, useState } from "react";

interface SessionSummary {
  session_id: string;
  started_at: string;
  title?: string | null;
}

interface Props {
  activeSessionId: string | null;
  onSelect: (id: string) => void;
}

export const SidebarSessions: React.FC<Props> = ({
  activeSessionId,
  onSelect,
}) => {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const loadSessions = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/sessions");
      const data = await res.json();
      setSessions(data);
    } catch (_) {
      setSessions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  return (
    <aside
      style={{
        width: "240px",
        borderRight: "1px solid #e5e7eb",
        background: "#f9fafb",
        padding: "12px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "8px" }}>
        Sessions
      </h2>

      {loading && <div style={{ fontSize: 12 }}>Loading…</div>}

      {!loading && sessions.length === 0 && (
        <div style={{ fontSize: 12, color: "#6b7280" }}>No sessions yet</div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
        {sessions.map((s) => (
          <button
            key={s.session_id}
            onClick={() => onSelect(s.session_id)}
            style={{
              textAlign: "left",
              padding: "6px 8px",
              borderRadius: 6,
              border:
                s.session_id === activeSessionId
                  ? "2px solid #2563eb"
                  : "1px solid #d1d5db",
              background:
                s.session_id === activeSessionId ? "#dbeafe" : "#ffffff",
              cursor: "pointer",
              fontSize: "0.8rem",
            }}
          >
            <div style={{ fontWeight: 600 }}>
              {s.title ?? "Untitled session"}
            </div>
            <div style={{ fontSize: 11, opacity: 0.7 }}>
              {new Date(s.started_at).toLocaleString()}
            </div>
          </button>
        ))}
      </div>
    </aside>
  );
};
