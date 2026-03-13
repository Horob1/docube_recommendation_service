"""
Embedding service — sentence-transformers wrapper.

Provides specialized encoding functions for documents, users, and queries
following the combined-text strategy from the spec.
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Model loaded lazily on first use
_model = None
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def get_model():
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(MODEL_NAME)
            logger.info("✅ Loaded sentence-transformer model: %s", MODEL_NAME)
        except Exception as e:
            logger.error("❌ Failed to load embedding model: %s", e)
            raise
    return _model


def encode_text(text: str) -> np.ndarray:
    """Encode a single text string into an embedding vector."""
    model = get_model()
    return model.encode(text, show_progress_bar=False)


def encode_document(
    title: Optional[str] = None,
    description: Optional[str] = None,
    content: Optional[str] = None,
    tags: list[str] = None,
    categories: list[str] = None,
    faculty: Optional[str] = None,
    author_display_name: Optional[str] = None,
) -> np.ndarray:
    """
    Build a combined text from document fields and encode it.

    Strategy:
        Title: {title}
        Description: {description}
        Tags: {tags joined}
        Categories: {categories joined}
        Faculty: {faculty}
        Content: {content[:2000]}
        Author: {author_display_name}
    """
    parts = []
    if title:
        parts.append(f"Title: {title}")
    if description:
        parts.append(f"Description: {description}")
    if tags:
        parts.append(f"Tags: {' '.join(tags)}")
    if categories:
        parts.append(f"Categories: {' '.join(categories)}")
    if faculty:
        parts.append(f"Faculty: {faculty}")
    if content:
        parts.append(f"Content: {content[:2000]}")
    if author_display_name:
        parts.append(f"Author: {author_display_name}")

    combined = "\n".join(parts) if parts else "empty document"
    return encode_text(combined)


def encode_user(
    username: Optional[str] = None,
    display_name: Optional[str] = None,
    role: Optional[str] = None,
    faculty: Optional[str] = None,
    interests: list[str] = None,
) -> np.ndarray:
    """
    Build a combined text from user profile fields and encode it.

    Strategy:
        Username: {username}
        Display Name: {displayName}
        Role: {role}
        Faculty: {faculty}
        Interests: {interests joined}
    """
    parts = []
    if username:
        parts.append(f"Username: {username}")
    if display_name:
        parts.append(f"Display Name: {display_name}")
    if role:
        parts.append(f"Role: {role}")
    if faculty:
        parts.append(f"Faculty: {faculty}")
    if interests:
        parts.append(f"Interests: {' '.join(interests)}")

    combined = "\n".join(parts) if parts else "new user"
    return encode_text(combined)


def encode_query(query: str) -> np.ndarray:
    """Encode a search query into an embedding vector."""
    return encode_text(query)


def blend_embeddings(
    old_embedding: Optional[np.ndarray],
    new_embedding: np.ndarray,
    weight: float,
) -> np.ndarray:
    """
    Blend two embeddings using weighted interpolation.

    new = old * (1 - weight) + new * weight

    If old_embedding is None, returns new_embedding directly.
    """
    if old_embedding is None:
        return new_embedding

    # Ensure numpy arrays
    old = np.array(old_embedding, dtype=np.float32)
    new = np.array(new_embedding, dtype=np.float32)

    blended = old * (1.0 - weight) + new * weight

    # Normalize to unit vector
    norm = np.linalg.norm(blended)
    if norm > 0:
        blended = blended / norm

    return blended


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))
