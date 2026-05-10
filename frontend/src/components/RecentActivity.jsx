import React, { useEffect, useState } from "react";

export default function RecentActivity({ apiBase = "" }) {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchRecent() {
      try {
        const r = await fetch(`${apiBase}/readings/recent?limit=20`);
        if (!r.ok) throw new Error(`status ${r.status}`);
        const data = await r.json();
        if (!cancelled) {
          setRows(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    fetchRecent();
    const id = setInterval(fetchRecent, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiBase]);

  const formatTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleTimeString();
  };

  if (error) return <div className="recent-error">recent activity unavailable: {error}</div>;
  if (!rows.length) return <div className="recent-empty">no readings yet</div>;

  return (
    <div className="recent-activity">
      <h3>Recent Activity</h3>
      <ul>
        {rows.map((row) => (
          <li key={row.id}>
            <span className="time">{formatTime(row.recorded_at)}</span>
            <span className="sensor">{row.sensor_name}</span>
            <span className="value">{row.value} {row.unit}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
