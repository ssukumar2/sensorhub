"""Simple threshold-based alerting for sensor readings."""
import logging
from dataclasses import dataclass, field

log = logging.getLogger("sensorhub.alerts")

@dataclass
class AlertRule:
    sensor_id: int
    metric: str
    threshold_high: float = None
    threshold_low: float = None
    triggered: bool = False

class AlertEngine:
    def __init__(self):
        self.rules: list[AlertRule] = []
        self.history: list[dict] = []

    def add_rule(self, rule: AlertRule):
        self.rules.append(rule)

    def evaluate(self, sensor_id: int, value: float, unit: str) -> list[dict]:
        alerts = []
        for rule in self.rules:
            if rule.sensor_id != sensor_id:
                continue
            if rule.threshold_high is not None and value > rule.threshold_high:
                alert = {"sensor_id": sensor_id, "value": value, "unit": unit,
                         "type": "high", "threshold": rule.threshold_high}
                alerts.append(alert)
                self.history.append(alert)
                log.warning("ALERT sensor=%d value=%.2f exceeds %.2f",
                            sensor_id, value, rule.threshold_high)
            if rule.threshold_low is not None and value < rule.threshold_low:
                alert = {"sensor_id": sensor_id, "value": value, "unit": unit,
                         "type": "low", "threshold": rule.threshold_low}
                alerts.append(alert)
                self.history.append(alert)
                log.warning("ALERT sensor=%d value=%.2f below %.2f",
                            sensor_id, value, rule.threshold_low)
        return alerts

    def get_history(self, limit: int = 50) -> list[dict]:
        return self.history[-limit:]

engine = AlertEngine()
