"""
Feature builder for offline training.

Extracts training features from user interactions and documents
to build feature vectors for the re-ranking model.
"""

import logging
from datetime import datetime, timezone

import numpy as np

from app.ml.embedding import cosine_similarity

logger = logging.getLogger(__name__)


def build_feature_from_sample(sample: dict) -> np.ndarray:
    """
    Build a feature vector from a training sample (joined interaction + document + user).

    Features:
        0: cosine similarity between user and document embeddings
        1: popularity score (log-normalized)
        2: recency score
        3: tag count (proxy for tag overlap)
        4: language match (0/1) — placeholder, always 0 for now
        5: role match (0/1)
    """
    import math

    # Cosine similarity
    user_emb = sample.get("user_embedding")
    doc_emb = sample.get("doc_embedding")

    if user_emb is not None and doc_emb is not None:
        sim = cosine_similarity(
            np.array(user_emb, dtype=np.float32),
            np.array(doc_emb, dtype=np.float32),
        )
    else:
        sim = 0.0

    # Popularity
    pop = sample.get("popularity_score", 0)
    popularity = math.log1p(pop) / 10.0

    # Recency
    created_at = sample.get("created_at")
    recency = _compute_recency(created_at)

    # Tag count as overlap proxy
    tags = sample.get("tags") or []
    tag_count = float(len(tags))

    # Language match — placeholder
    lang_match = 0.0

    # Role match
    user_role = sample.get("user_role", "")
    author_role = sample.get("author_role", "")
    role_match = 1.0 if (user_role and author_role and user_role == author_role) else 0.0

    return np.array([sim, popularity, recency, tag_count, lang_match, role_match], dtype=np.float32)


def build_features_batch(samples: list[dict]) -> np.ndarray:
    """Build feature matrix from a batch of samples."""
    if not samples:
        return np.empty((0, 6), dtype=np.float32)
    return np.array([build_feature_from_sample(s) for s in samples], dtype=np.float32)


def _compute_recency(dt) -> float:
    """Compute recency score (0–1) with 30-day half-life."""
    import math

    if dt is None:
        return 0.5

    now = datetime.now(timezone.utc)
    if hasattr(dt, "tzinfo") and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    age_days = (now - dt).total_seconds() / 86400.0
    return max(0.0, min(1.0, math.exp(-0.693 * age_days / 30.0)))
