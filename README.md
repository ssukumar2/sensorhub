# sensorhub

A small, experimental secure sensor network gateway. Sensors register with the
gateway, submit telemetry readings, and a REST API exposes the data for
querying.

This is a learning project: I'm building it to explore backend design, IoT
ingestion patterns, and (in later iterations) authenticated device
communication and MQTT ingestion.

Working endpoints:

 `GET  /health` : liveness probe
 `POST /sensors` : register a new sensor
 `GET  /sensors` : list all sensors
 `GET  /sensors/{id}` : get one sensor
`POST /readings` : submit a telemetry reading `   (requires x-api-key header)
- `GET  /sensors/{id}/readings`: list recent readings for a sensor

# Status Progress
No authentication yet.
progress update: Basic API key authentication is in place: each sensor gets its own key, and readings require the correct key in the `x-api-key` header.


# Stack

 Python 3.8+
 FastAPI
SQLModel (SQLAlchemy + Pydantic)
SQLite
 Uvicorn

# Running it locally

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