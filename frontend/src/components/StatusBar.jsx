import React from 'react';

export default function StatusBar({ status, sensorCount }) {
  const online = status && status.status === 'ok';
  return (
    <div className="status-bar">
      <span className={`indicator ${online ? 'online' : 'offline'}`} />
      <span>{online ? 'Backend online' : 'Backend offline'}</span>
      <span className="sensor-count">{sensorCount} sensors</span>
    </div>
  );
}