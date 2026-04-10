# sensorhub

A small, experimental secure sensor network gateway. Sensors register with the
gateway, submit telemetry readings, and a REST API exposes the data for
querying.

This is a learning project — I'm building it to explore backend design, IoT
ingestion patterns, and (in later iterations) authenticated device
communication and MQTT ingestion.

## Current status

* Refactor database module for testability.**

Working endpoints:

- `GET  /health` — liveness probe
- `POST /sensors` — register a new sensor
- `GET  /sensors` — list all sensors
- `GET  /sensors/{id}` — get one sensor
- `POST /readings` — submit a telemetry reading
- `GET  /sensors/{id}/readings` — list recent readings for a sensor

No authentication yet. That's coming next.

## Planned next steps

- HMAC-based device authentication (shared key per sensor)
- Replay protection with nonces and timestamps
- MQTT ingestion alongside HTTP
- Simulated sensor clients in Python and C
- A small dashboard (TypeScript / React) for live data
- Threat model document

## Stack

- Python 3.8+
- FastAPI
- SQLModel (SQLAlchemy + Pydantic)
- SQLite
- Uvicorn

## Running it locally

```bash
git clone git@github.com:ssukumar2/sensorhub.git
cd sensorhub
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open http://localhost:8000/docs for the interactive API docs.

## License

MIT