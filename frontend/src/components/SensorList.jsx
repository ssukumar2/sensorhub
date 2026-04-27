import React from 'react';

export default function SensorList({ sensors, onSelect, selected }) {
  return (
    <div className="sensor-list">
      <h2>Sensors</h2>
      <table>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Location</th></tr>
        </thead>
        <tbody>
          {sensors.map(s => (
            <tr key={s.id} onClick={() => onSelect(s.id)}
                className={selected === s.id ? 'selected' : ''}>
              <td>{s.id}</td><td>{s.name}</td><td>{s.location}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
