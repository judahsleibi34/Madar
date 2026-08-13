from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.errors import ApiError

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)
_dummy_hash = _hasher.hash("not-a-real-user-password-2026!")


def validate_password(password: str, *, minimum_length: int) -> None:
    if len(password) < minimum_length or len(password) > 128:
        raise ApiError(422, "INVALID_PASSWORD", "The password does not meet security requirements.")
    categories = (
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"\d", password)),
        bool(re.search(r"[^A-Za-z0-9]", password)),
    )
    if sum(categories) < 3:
        raise ApiError(422, "INVALID_PASSWORD", "The password does not meet security requirements.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    target = password_hash or _dummy_hash
    try:
        valid = _hasher.verify(target, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    return bool(valid and password_hash)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
