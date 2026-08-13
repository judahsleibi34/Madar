from __future__ import annotations

import hashlib
import json

RANKING_IMPLEMENTATION_VERSION = "top-k-mean-v1"


def ranking_cache_key(
    baseline_sha256: str,
    normalized_text_hash: str,
    chunk_config_hash: str,
    model_id: str,
    model_version: str,
    backend: str,
    top_k: int,
    matching_excerpt_count: int = 3,
) -> str:
    value = {
        "baseline": baseline_sha256,
        "document": normalized_text_hash,
        "chunks": chunk_config_hash,
        "model": model_id,
        "version": model_version,
        "backend": backend,
        "top_k": top_k,
        "matching_excerpt_count": matching_excerpt_count,
        "implementation": RANKING_IMPLEMENTATION_VERSION,
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
