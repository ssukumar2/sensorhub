import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function ReadingsChart({ sensorId, api }) {
  const [readings, setReadings] = useState([]);

  useEffect(() => {
    fetch(`${api}/sensors/${sensorId}/readings`)
      .then(r => r.json())
      .then(data => setReadings(data.slice(-50)))
      .catch(() => {});
  }, [sensorId, api]);

  return (
    <div className="readings-chart">
      <h2>Readings for sensor {sensorId}</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={readings}>
          <XAxis dataKey="id" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="value" stroke="#4a90d9" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
