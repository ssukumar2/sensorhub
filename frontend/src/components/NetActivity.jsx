import React, { useEffect, useState } from 'react';

export default function NetActivity({ apiBase = '' }) {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const h = await fetch(`${apiBase}/net/health`).then(r => r.json());
        if (!cancelled) setHealth(h);
      } catch {}
    }
    load();
    const id = setInterval(load, 3000);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiBase]);

  if (!health) return <div className="net-activity">Loading transport stats…</div>;

  const Row = ({ name, data, primaryKey, primaryLabel }) => (
    <tr>
      <td>{name}</td>
      <td>{data[primaryKey]}</td>
      <td>{data.errors}</td>
      <td>{data.error_pct}%</td>
    </tr>
  );

  return (
    <div className="net-activity">
      <h3>Network Transport</h3>
      <table>
        <thead>
          <tr><th>Channel</th><th>Volume</th><th>Errors</th><th>Error %</th></tr>
        </thead>
        <tbody>
          <Row name="CAN" data={health.can} primaryKey="frames" primaryLabel="frames" />
          <Row name="UDP" data={health.udp} primaryKey="packets" primaryLabel="packets" />
          <Row name="TCP" data={health.tcp} primaryKey="readings" primaryLabel="readings" />
        </tbody>
      </table>
      <p>TCP active connections: <strong>{health.tcp.active}</strong></p>
    </div>
  );
}
