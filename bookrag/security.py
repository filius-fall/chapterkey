"""Security helpers for passwords, tokens, and encrypted secrets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from typing import Tuple


def hash_password(password: str, salt: bytes | None = None) -> Tuple[str, str]:
    """Hash a password with PBKDF2."""
    salt = salt or os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return base64.b64encode(salt).decode("utf-8"), base64.b64encode(password_hash).decode("utf-8")


def verify_password(password: str, salt_b64: str, password_hash_b64: str) -> bool:
    """Verify a password against the stored hash."""
    salt = base64.b64decode(salt_b64.encode("utf-8"))
    _, candidate_hash = hash_password(password, salt=salt)
    return hmac.compare_digest(candidate_hash, password_hash_b64)


def issue_token() -> str:
    """Generate a user-facing token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash an API or session token for storage."""
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("utf-8")


def _keystream(secret: str, nonce: bytes, length: int) -> bytes:
    """Create a deterministic keystream from the app secret and nonce."""
    secret_bytes = secret.encode("utf-8")
    output = bytearray()
    counter = 0
    while len(output) < length:
        block = hashlib.sha256(secret_bytes + nonce + counter.to_bytes(4, "big")).digest()
        output.extend(block)
        counter += 1
    return bytes(output[:length])


def encrypt_secret(value: str, app_secret: str) -> str:
    """Encrypt a stored provider key using a simple authenticated envelope."""
    plaintext = value.encode("utf-8")
    nonce = os.urandom(16)
    stream = _keystream(app_secret, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
    mac = hmac.new(app_secret.encode("utf-8"), nonce + ciphertext, hashlib.sha256).digest()
    payload = nonce + ciphertext + mac
    return base64.b64encode(payload).decode("utf-8")


def decrypt_secret(payload_b64: str, app_secret: str) -> str:
    """Decrypt a provider key previously encrypted with encrypt_secret."""
    payload = base64.b64decode(payload_b64.encode("utf-8"))
    nonce = payload[:16]
    mac = payload[-32:]
    ciphertext = payload[16:-32]
    expected_mac = hmac.new(app_secret.encode("utf-8"), nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("Stored secret failed integrity validation")
    stream = _keystream(app_secret, nonce, len(ciphertext))
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, stream))
    return plaintext.decode("utf-8")
