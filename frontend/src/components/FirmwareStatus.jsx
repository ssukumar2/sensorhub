import React, { useEffect, useState } from 'react';

export default function FirmwareStatus({ apiBase = '' }) {
  const [devices, setDevices] = useState([]);
  const [latest, setLatest] = useState({ version: '', url: '' });
  const [versions, setVersions] = useState([]);

  async function load() {
    try {
      const [d, l, v] = await Promise.all([
        fetch(`${apiBase}/firmware/devices`).then(r => r.json()),
        fetch(`${apiBase}/firmware/latest`).then(r => r.json()),
        fetch(`${apiBase}/firmware/versions`).then(r => r.json()),
      ]);
      setDevices(d);
      setLatest(l);
      setVersions(v);
    } catch {}
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, [apiBase]);

  async function handleDelete(version) {
    if (!window.confirm(`Delete firmware ${version}?`)) return;
    await fetch(`${apiBase}/firmware/${version}`, { method: 'DELETE' });
    load();
  }

  return (
    <div className="firmware-status">
      <h3>Firmware</h3>
      <p>Latest available: <strong>{latest.version || 'none'}</strong></p>

      <h4>Uploaded versions</h4>
      {versions.length === 0 ? (
        <p>No firmware uploaded.</p>
      ) : (
        <table>
          <thead>
            <tr><th>Version</th><th>Size</th><th>SHA256</th><th></th></tr>
          </thead>
          <tbody>
            {versions.map(v => (
              <tr key={v.version}>
                <td>{v.version}</td>
                <td>{v.size} B</td>
                <td><code>{v.sha256.slice(0, 12)}…</code></td>
                <td><button onClick={() => handleDelete(v.version)}>delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h4>Devices</h4>
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
