"""Authentication and authorization utilities for Relay Gateway."""

import base64
import hmac


def verify_relay_token(provided_token: str | None, required_secret: str | None) -> bool:
    """Verifies client authentication token against the relay secret."""
    if not required_secret:
        # Relay does not require authentication
        return True
    if not provided_token:
        return False
    return hmac.compare_digest(provided_token, required_secret)


def verify_basic_auth(auth_header: str | None, expected_credentials: str | None) -> bool:
    """Verifies incoming HTTP Basic Authentication header against expected 'user:password'."""
    if not expected_credentials:
        # No basic auth required for this tunnel
        return True
    if not auth_header or not auth_header.lower().startswith("basic "):
        return False

    try:
        encoded_creds = auth_header.split(" ", 1)[1].strip()
        decoded = base64.b64decode(encoded_creds).decode("utf-8")
        return hmac.compare_digest(decoded, expected_credentials)
    except Exception:
        return False
