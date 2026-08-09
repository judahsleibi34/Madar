from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol


class Tokenizer(Protocol):
    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]: ...
    def decode(self, tokens: list[int], skip_special_tokens: bool = True) -> str: ...


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    token_count: int
    sha256: str


def chunk_config_hash(
    size: int, overlap: int, model_id: str, model_version: str = "default"
) -> str:
    payload = json.dumps(
        {"size": size, "overlap": overlap, "model": model_id, "version": model_version},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def chunk_text(text: str, tokenizer: Tokenizer, size: int, overlap: int) -> list[TextChunk]:
    tokens = tokenizer.encode(text, add_special_tokens=False)
    if not tokens:
        return []
    step = size - overlap
    result: list[TextChunk] = []
    seen: set[str] = set()
    for start in range(0, len(tokens), step):
        selected = tokens[start : start + size]
        rendered = tokenizer.decode(selected, skip_special_tokens=True).strip()
        digest = hashlib.sha256(rendered.encode()).hexdigest()
        if rendered and digest not in seen:
            result.append(TextChunk(len(result), rendered, len(selected), digest))
            seen.add(digest)
        if start + size >= len(tokens):
            break
    return result
