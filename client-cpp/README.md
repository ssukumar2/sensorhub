# sensor-client

C++ simulator that acts as a sensor device. Connects to the sensorhub backend,
registers itself, and pushes fake telemetry readings.

## Building

Open `client-cpp/` :

    cmake -B build
    cmake --build build

## Running

    ./build/sensor_client

## Security

The system implements layered security for sensor communication:

**Authentication:**
- Each sensor gets a unique API key on registration
- Readings require the correct key in the `x-api-key` header
- Server uses constant-time comparison to prevent timing attacks

**Integrity (HMAC signing):**
- C++ client signs every reading payload with HMAC-SHA256
- Signature covers: JSON body + nonce + timestamp
- Server verifies the signature if present
- Tampering with the payload, nonce, or timestamp invalidates the signature

**Replay protection:**
- Each request carries a unique random nonce (128-bit hex)
- Each request carries a unix timestamp
- Server rejects requests older than 30 seconds
- Prevents captured requests from being replayed later

**Planned:**
- TLS for HTTP and MQTT transport
- MQTT username/password and client certificate authentication
- Per-sensor rate limiting
- Audit logging of authentication events