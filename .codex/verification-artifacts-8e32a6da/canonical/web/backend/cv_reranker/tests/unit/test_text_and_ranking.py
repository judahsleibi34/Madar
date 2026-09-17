from __future__ import annotations

import math

import pytest

from app.services.ranking.cache import ranking_cache_key
from app.services.ranking.reranker import aggregate_scores
from app.services.text_processing.chunking import chunk_text
from app.services.text_processing.normalization import normalize_text


class WordTokenizer:
    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        del add_special_tokens
        self.words = text.split()
        return list(range(len(self.words)))

    def decode(self, tokens: list[int], skip_special_tokens: bool = True) -> str:
        del skip_special_tokens
        return " ".join(self.words[index] for index in tokens)


def test_normalization_is_deterministic() -> None:
    assert normalize_text(" A\t B\r\n\r\n\r\nC ") == "A B\n\nC"


def test_token_chunks_overlap_and_deduplicate() -> None:
    chunks = chunk_text("one two three four five six", WordTokenizer(), size=4, overlap=2)
    assert [chunk.text for chunk in chunks] == [
        "one two three four",
        "three four five six",
    ]
    assert [chunk.token_count for chunk in chunks] == [4, 4]


def test_cache_key_changes_with_model_configuration() -> None:
    first = ranking_cache_key("a", "b", "c", "model", "v1", "onnx", 3)
    assert first == ranking_cache_key("a", "b", "c", "model", "v1", "onnx", 3)
    assert first != ranking_cache_key("a", "b", "c", "model", "v2", "onnx", 3)


def test_top_k_mean_keeps_raw_score_semantics() -> None:
    assert aggregate_scores([-3.0, 0.2, 4.0], 2) == pytest.approx(2.1)
    assert math.isfinite(aggregate_scores([1.0], 3))
