from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any, Protocol

from app.core.config import Settings


class Reranker(Protocol):
    model_id: str
    model_version: str
    backend: str
    tokenizer: Any

    def predict(self, pairs: Sequence[tuple[str, str]], batch_size: int) -> list[float]: ...


class SentenceTransformerReranker:
    def __init__(self, settings: Settings) -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as error:
            raise RuntimeError(
                "Install the 'model' dependency extra to run the ranking worker."
            ) from error
        self.model_id = settings.rerank_model_id
        self.model_version = settings.rerank_model_version
        self.backend = settings.rerank_backend
        kwargs: dict[str, object] = {"cache_folder": str(settings.model_cache_directory)}
        if self.backend == "onnx":
            kwargs["backend"] = "onnx"
        try:
            self._model = CrossEncoder(self.model_id, **kwargs)
        except Exception:
            if self.backend != "onnx":
                raise
            self.backend = "pytorch"
            self._model = CrossEncoder(
                self.model_id, cache_folder=str(settings.model_cache_directory)
            )
        self.tokenizer = self._model.tokenizer

    def predict(self, pairs: Sequence[tuple[str, str]], batch_size: int) -> list[float]:
        values = self._model.predict(list(pairs), batch_size=batch_size, show_progress_bar=False)
        scores = [float(value) for value in values]
        if not all(math.isfinite(value) for value in scores):
            raise RuntimeError("The reranker produced a non-finite score.")
        return scores


def aggregate_scores(scores: Sequence[float], top_k: int) -> float:
    if not scores:
        raise ValueError("At least one chunk score is required.")
    selected = sorted(scores, reverse=True)[:top_k]
    return sum(selected) / len(selected)
