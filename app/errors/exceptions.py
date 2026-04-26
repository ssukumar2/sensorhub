"""Custom exception types for sensorhub."""


class SensorhubError(Exception):
    """Base exception for all sensorhub errors."""


class SensorNotFoundError(SensorhubError):
    def __init__(self, sensor_id: int):
        super().__init__(f"sensor {sensor_id} not found")
        self.sensor_id = sensor_id


class AuthenticationError(SensorhubError):
    def __init__(self, detail: str = "invalid credentials"):
        super().__init__(detail)


class SignatureVerificationError(AuthenticationError):
    def __init__(self):
        super().__init__("HMAC signature verification failed")


class ReplayAttackError(AuthenticationError):
    def __init__(self):
        super().__init__("request timestamp expired or nonce reused")


class RateLimitError(SensorhubError):
    def __init__(self, limit: int):
        super().__init__(f"rate limit exceeded: max {limit} requests per minute")
        self.limit = limit