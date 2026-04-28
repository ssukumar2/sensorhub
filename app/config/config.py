import os

class Settings:
    DB_URL: str = os.getenv("SENSORHUB_DB", "sqlite:///sensorhub.db")
    API_KEY_LENGTH: int = int(os.getenv("SENSORHUB_KEY_LEN", "32"))
    HMAC_MAX_AGE_SEC: int = int(os.getenv("SENSORHUB_HMAC_AGE", "30"))
    RATE_LIMIT_PER_MIN: int = int(os.getenv("SENSORHUB_RATE_LIMIT", "60"))
    MQTT_BROKER: str = os.getenv("SENSORHUB_MQTT_HOST", "localhost")
    MQTT_PORT: int = int(os.getenv("SENSORHUB_MQTT_PORT", "1883"))
    MQTT_TOPIC_PREFIX: str = "sensorhub/sensors"
    CAN_INTERFACE: str = os.getenv("SENSORHUB_CAN_IF", "vcan0")
    LOG_LEVEL: str = os.getenv("SENSORHUB_LOG_LEVEL", "INFO")

settings = Settings()
