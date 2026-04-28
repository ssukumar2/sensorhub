import hashlib
import hmac
import time
import secrets

_used_nonces: set = set()
_MAX_NONCES = 10000

def generate_api_key(length: int = 32) -> str:
    return secrets.token_hex(length)

def compute_hmac(key: str, payload: str, nonce: str, timestamp: str) -> str:
    message = f"{payload}:{nonce}:{timestamp}"
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()

def verify_hmac(key: str, payload: str, nonce: str, timestamp: str,
                signature: str, max_age: int = 30) -> bool:
    age = abs(time.time() - float(timestamp))
    if age > max_age:
        return False

    if nonce in _used_nonces:
        return False

    expected = compute_hmac(key, payload, nonce, timestamp)
    if not hmac.compare_digest(expected, signature):
        return False

    _used_nonces.add(nonce)
    if len(_used_nonces) > _MAX_NONCES:
        _used_nonces.clear()

    return True
