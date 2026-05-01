"""MQTT topic routing and handler dispatch."""
import re
import logging
from typing import Callable

log = logging.getLogger("sensorhub.mqtt.router")

class MqttRouter:
    def __init__(self):
        self._routes: list[tuple[str, re.Pattern, Callable]] = []

    def route(self, pattern: str):
        """Register a handler for a topic pattern.
        Use {name} for named captures, + for single level, # for multi level.
        """
        regex = pattern.replace("+", "([^/]+)").replace("#", "(.+)")
        regex = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", regex)
        compiled = re.compile(f"^{regex}$")

        def decorator(func: Callable):
            self._routes.append((pattern, compiled, func))
            log.info("registered handler for %s", pattern)
            return func
        return decorator

    def dispatch(self, topic: str, payload: bytes) -> bool:
        for pattern, regex, handler in self._routes:
            match = regex.match(topic)
            if match:
                try:
                    handler(topic, payload, **match.groupdict())
                    return True
                except Exception as e:
                    log.error("handler error for %s: %s", topic, e)
                    return False
        log.debug("no handler for topic: %s", topic)
        return False

router = MqttRouter()

@router.route("sensorhub/sensors/{sensor_id}/readings")
def handle_reading(topic: str, payload: bytes, sensor_id: str):
    import json
    data = json.loads(payload)
    log.info("reading from sensor %s: %s", sensor_id, data)

@router.route("sensorhub/sensors/{sensor_id}/status")
def handle_status(topic: str, payload: bytes, sensor_id: str):
    log.info("status from sensor %s: %s", sensor_id, payload.decode())

@router.route("sensorhub/system/#")
def handle_system(topic: str, payload: bytes):
    log.info("system message on %s: %s", topic, payload.decode())
