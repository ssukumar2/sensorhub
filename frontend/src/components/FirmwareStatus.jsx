import React, { useEffect, useState } from 'react';

export default function FirmwareStatus({ apiBase = '' }) {
  const [devices, setDevices] = useState([]);
  const [latest, setLatest] = useState({ version: '', url: '' });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [d, l] = await Promise.all([
          fetch(`${apiBase}/firmware/devices`).then(r => r.json()),
          fetch(`${apiBase}/firmware/latest`).then(r => r.json()),
        ]);
        if (!cancelled) {
          setDevices(d);
          setLatest(l);
        }
      } catch {}
    }
    load();
    const id = setInterval(load, 10000);
    return () => { cancelled = true; clearInterval(id); };
  }, [apiBase]);

  return (
    <div className="firmware-status">
      <h3>Firmware</h3>
      <p>Latest available: <strong>{latest.version || 'none'}</strong></p>
      {devices.length === 0 ? (
        <p>No devices reporting yet.</p>
      ) : (
        <table>
          <thead>
            <tr><th>Sensor</th><th>Version</th><th>Built</th><th>Status</th></tr>
          </thead>
          <tbody>
            {devices.map(d => (
              <tr key={d.sensor_id}>
                <td>{d.sensor_id}</td>
                <td>{d.version}</td>
                <td>{d.build_date || '-'}</td>
                <td>{d.version === latest.version ? '✓ current' : '⚠ outdated'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
