import React, { useState, useEffect } from 'react';
import StatusBar from './components/StatusBar';
import SensorList from './components/SensorList';
import ReadingsChart from './components/ReadingsChart';
import RecentActivity from "./components/RecentActivity";
import './App.css';

const API = 'http://localhost:8000';

export default function App() {
  const [sensors, setSensors] = useState([]);
  const [selected, setSelected] = useState(null);
  const [status, setStatus] = useState(null);

  useEffect(() => {
    fetch(`${API}/health`).then(r => r.json()).then(setStatus).catch(() => setStatus(null));
    fetch(`${API}/sensors`).then(r => r.json()).then(setSensors).catch(() => {});
  }, []);

  return (
    <div className="app">
      <header className="header">
        <h1>sensorhub dashboard</h1>
        <StatusBar status={status} sensorCount={sensors.length} />
      </header>
      <main className="main">
        <SensorList sensors={sensors} onSelect={setSelected} selected={selected} />
        {selected && <ReadingsChart sensorId={selected} api={API} />}
      </main>
      <RecentActivity />
    </div>
  );
}