"""
A/B testing configuration.

Defines weight profiles for different A/B groups
used in the hybrid scoring pipeline.
"""

from dataclasses import dataclass


@dataclass
class ABWeights:
    """Weight configuration for hybrid scoring."""
    similarity: float
    popularity: float
    tag: float
    recency: float


# ── A/B Group Configurations ─────────────────────────────────────────

AB_CONFIGS: dict[str, ABWeights] = {
    "A": ABWeights(
        similarity=0.6,
        popularity=0.2,
        tag=0.1,
        recency=0.1,
    ),
    "B": ABWeights(
        similarity=0.7,
        popularity=0.1,
        tag=0.1,
        recency=0.1,
    ),
}

# Default fallback
DEFAULT_WEIGHTS = AB_CONFIGS["A"]


def get_weights(ab_group: str) -> ABWeights:
    """Get the weight configuration for an A/B group."""
    return AB_CONFIGS.get(ab_group, DEFAULT_WEIGHTS)
