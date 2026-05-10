import React, { useEffect, useState } from 'react';

export default function Header({ apiBase = '' }) {
  const [counts, setCounts] = useState({ sensors: null, readings: null });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [sr, rr] = await Promise.all([
          fetch(`${apiBase}/sensors/count`).then(r => r.json()),
          fetch(`${apiBase}/readings/count`).then(r => r.json()),
        ]);
        if (!cancelled) setCounts({ sensors: sr.count, readings: rr.count });
      } catch {
        if (!cancelled) setCounts({ sensors: '?', readings: '?' });
      }
    }
    load();
    const id = setInterval(load, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiBase]);

  return (
    <header className="app-header">
      <h1>SensorHub</h1>
      <div className="stats">
        <span>{counts.sensors ?? '…'} sensors</span>
        <span>{counts.readings ?? '…'} readings</span>
      </div>
    </header>
  );
}
