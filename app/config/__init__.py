"""Centralized configuration for sensorhub."""

import os


class Config:
    """Application configuration loaded from environment variables with defaults."""

    DATABASE_URL: str = os.getenv("SENSORHUB_DB_URL", "sqlite:///./sensorhub.db")
    MQTT_BROKER_HOST: str = os.getenv("SENSORHUB_MQTT_HOST", "localhost")
    MQTT_BROKER_PORT: int = int(os.getenv("SENSORHUB_MQTT_PORT", "1883"))
    MQTT_TOPIC_PATTERN: str = os.getenv("SENSORHUB_MQTT_TOPIC", "sensorhub/sensors/+/readings")
    MAX_TIMESTAMP_AGE_SECONDS: int = int(os.getenv("SENSORHUB_MAX_TS_AGE", "30"))
    API_VERSION: str = "0.1.0"
    SERVICE_NAME: str = "sensorhub"


config = Config()