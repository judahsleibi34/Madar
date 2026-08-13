from __future__ import annotations

import uuid

import pytest

from app.auth.password import hash_password, validate_password, verify_password
from app.auth.tokens import create_access_token, decode_access_token
from app.core.config import get_settings
from app.core.errors import ApiError


def test_password_hash_and_verify() -> None:
    encoded = hash_password("Correct-Horse-Battery-42")
    assert "Correct-Horse-Battery-42" not in encoded
    assert verify_password("Correct-Horse-Battery-42", encoded)
    assert not verify_password("wrong-password", encoded)


def test_weak_password_is_rejected() -> None:
    with pytest.raises(ApiError):
        validate_password("password1234", minimum_length=12)


def test_access_token_is_scoped_and_tamper_evident() -> None:
    settings = get_settings()
    user_id = uuid.uuid4()
    encoded = create_access_token(user_id, settings).token
    assert decode_access_token(encoded, settings) == user_id
    with pytest.raises(ApiError):
        decode_access_token(encoded + "x", settings)
