"""
Database setup for beaconnet.

Uses SQLite via SQLModel. The database file is created in the project root
as `beaconnet.db` the first time the app runs.
"""
from sqlmodel import SQLModel, create_engine, Session

#DATABASE_URL = "sqlite:///./sensorhub.db"

# echo=False so we don't spam the terminal with SQL.
# Set it to True temporarily if you want to see every query.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create all tables. Safe to call multiple times."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency that yields a database session per request."""
    with Session(engine) as session:
        yield session