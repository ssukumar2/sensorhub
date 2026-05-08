import React, { useEffect, useState } from 'react';

export default function SensorList({ sensors, onSelect, selected, apiBase = '' }) {
  const [latest, setLatest] = useState({});

  useEffect(() => {
    let cancelled = false;
    async function loadAll() {
      const next = {};
      await Promise.all(sensors.map(async (s) => {
        try {
          const r = await fetch(`${apiBase}/sensors/${s.id}/latest`);
          if (r.ok) next[s.id] = await r.json();
          else next[s.id] = null;
        } catch {
          next[s.id] = null;
        }
      }));
      if (!cancelled) setLatest(next);
    }
    if (sensors.length) loadAll();
    return () => { cancelled = true; };
  }, [sensors, apiBase]);

  const fmt = (row) => row ? `${row.value} ${row.unit}` : '—';

  return (
    <div className="sensor-list">
      <h2>Sensors</h2>
      <table>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Location</th><th>Latest</th></tr>
        </thead>
        <tbody>
          {sensors.map(s => (
            <tr key={s.id} onClick={() => onSelect(s.id)}
                className={selected === s.id ? 'selected' : ''}>
              <td>{s.id}</td>
              <td>{s.name}</td>
              <td>{s.location}</td>
              <td>{fmt(latest[s.id])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
