from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
from datetime import timedelta
from typing import Optional

import jwt

from app.core.config import get_settings
from app.models import User, utcnow

log = logging.getLogger("scholarscope.security")
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}
_ephemeral_secret: Optional[str] = None


def secret_key() -> str:
    global _ephemeral_secret
    s = get_settings()
    if s.secret_key:
        if len(s.secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters")
        return s.secret_key
    if s.is_production:
        raise RuntimeError("SECRET_KEY must be set in production")
    if _ephemeral_secret is None:
        _ephemeral_secret = secrets.token_urlsafe(48)
        log.warning("SECRET_KEY not set; using an ephemeral key (all sessions end when the server restarts)")
    return _ephemeral_secret


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    return "scrypt${n}${r}${p}${salt}${hash}".format(
        **_SCRYPT, salt=base64.b64encode(salt).decode(), hash=base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, n, r, p, salt, digest = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), dklen=32, n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(calc, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def create_token(user: User) -> str:
    now = utcnow()
    payload = {"sub": user.id, "role": user.role, "iat": now,
               "exp": now + timedelta(minutes=get_settings().token_ttl_minutes)}
    return jwt.encode(payload, secret_key(), algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, secret_key(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
