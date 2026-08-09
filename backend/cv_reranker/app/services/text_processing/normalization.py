from __future__ import annotations

import hashlib
import re
import unicodedata

NORMALIZATION_VERSION = "nfkc-ws-v1"


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\x00", " ")
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r"\r\n?|\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
