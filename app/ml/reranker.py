"""
Re-ranking module.

Loads a trained model (LightGBM or LogisticRegression fallback)
and re-ranks candidate documents by predicted engagement probability.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)

_model = None
_model_type: str = "none"

DEFAULT_MODEL_PATH = Path("models/reranker.pkl")


def load_model(model_path: Optional[str] = None) -> None:
    """
    Load the re-ranking model from disk.

    Falls back to a simple LogisticRegression if no trained model exists.
    Called once during application startup.
    """
    global _model, _model_type

    path = Path(model_path) if model_path else DEFAULT_MODEL_PATH

    if path.exists():
        try:
            _model = joblib.load(path)
            _model_type = type(_model).__name__
            logger.info("✅ Loaded reranker model: %s from %s", _model_type, path)
            return
        except Exception as e:
            logger.warning("⚠️  Failed to load model from %s: %s", path, e)

    # Fallback: untrained LogisticRegression
    _model = LogisticRegression()
    _model_type = "LogisticRegression (fallback, untrained)"
    logger.info("ℹ️  Using fallback reranker: %s", _model_type)


def build_feature_vector(
    similarity: float,
    popularity: float,
    recency: float,
    tag_overlap: int,
    language_match: bool,
    role_match: bool,
) -> np.ndarray:
    """
    Build a feature vector for a single candidate.

    Features:
        0: cosine similarity
        1: popularity score (normalized)
        2: recency score (0–1)
        3: tag overlap count
        4: language match (0/1)
        5: role match (0/1)
    """
    return np.array([
        similarity,
        popularity,
        recency,
        float(tag_overlap),
        1.0 if language_match else 0.0,
        1.0 if role_match else 0.0,
    ], dtype=np.float32)


def rerank(
    candidates: list[dict],
    feature_vectors: np.ndarray,
    top_k: int = 20,
) -> list[dict]:
    """
    Re-rank candidates using the loaded model.

    If the model is trained, use predict_proba for scoring.
    Otherwise, return candidates as-is (sorted by hybrid_score).

    Args:
        candidates: List of candidate dicts with 'hybrid_score'.
        feature_vectors: (N, 6) numpy array of feature vectors.
        top_k: Number of results to return.

    Returns:
        Top-k candidates re-ranked by model prediction.
    """
    global _model, _model_type

    if _model is None:
        load_model()

    # Check if model is fitted
    try:
        if hasattr(_model, "classes_") or hasattr(_model, "booster_"):
            # Model is trained — predict engagement probability
            if hasattr(_model, "predict_proba"):
                scores = _model.predict_proba(feature_vectors)[:, 1]
            else:
                scores = _model.predict(feature_vectors)

            # Combine model score with hybrid score
            for i, candidate in enumerate(candidates):
                candidate["rerank_score"] = float(scores[i])
                candidate["final_score"] = (
                    0.6 * candidate.get("hybrid_score", 0) +
                    0.4 * float(scores[i])
                )

            candidates.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        else:
            # Model not trained yet — use hybrid score directly
            candidates.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)

    except Exception as e:
        logger.warning("⚠️  Reranker failed, using hybrid scores: %s", e)
        candidates.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)

    return candidates[:top_k]


def get_model_info() -> dict:
    """Get info about the current reranker model."""
    return {
        "model_type": _model_type,
        "is_trained": _model is not None and (
            hasattr(_model, "classes_") or hasattr(_model, "booster_")
        ),
    }
