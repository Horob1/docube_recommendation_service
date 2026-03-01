"""
Offline training pipeline — CLI entry point.

Extracts interaction data from PostgreSQL, builds features,
trains the re-ranking model, and saves it to disk.

Usage:
    python -m app.training.offline_pipeline
    python -m app.training.offline_pipeline --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def run_pipeline(dry_run: bool = False, model_path: str = None) -> dict:
    """
    Full offline training pipeline:
    1. Initialize DB connection
    2. Extract positive samples (buy/bookmark)
    3. Extract negative samples (view-only)
    4. Build feature vectors
    5. Train model
    6. Save model to disk
    """
    from app.repositories.database import init_db_pool, close_db_pool
    from app.repositories import interaction_repo
    from app.training.feature_builder import build_features_batch
    from app.training.model_trainer import train_model, DEFAULT_MODEL_PATH

    path = Path(model_path) if model_path else DEFAULT_MODEL_PATH

    logger.info("🏭 Starting offline training pipeline ...")

    # 1. Init DB
    await init_db_pool()

    try:
        # 2. Extract positive samples
        logger.info("📊 Extracting positive samples (buy/bookmark) ...")
        positive_samples = await interaction_repo.get_positive_samples()
        logger.info("  → %d positive samples", len(positive_samples))

        # 3. Extract negative samples
        logger.info("📊 Extracting negative samples (view-only) ...")
        negative_samples = await interaction_repo.get_negative_samples(
            limit=len(positive_samples) * 2,  # 2:1 neg:pos ratio
        )
        logger.info("  → %d negative samples", len(negative_samples))

        total = len(positive_samples) + len(negative_samples)
        if total < 20:
            logger.warning("⚠️  Only %d total samples — not enough to train.", total)
            return {"status": "skipped", "reason": "insufficient data", "total_samples": total}

        if dry_run:
            logger.info("🔍 DRY RUN — would train with %d samples. Exiting.", total)
            return {"status": "dry_run", "positive": len(positive_samples), "negative": len(negative_samples)}

        # 4. Build feature vectors
        logger.info("🔧 Building feature vectors ...")
        X_pos = build_features_batch(positive_samples)
        X_neg = build_features_batch(negative_samples)

        X = np.vstack([X_pos, X_neg])
        y = np.concatenate([
            np.ones(len(X_pos)),
            np.zeros(len(X_neg)),
        ])

        logger.info("  → Feature matrix shape: %s", X.shape)

        # 5. Train model
        logger.info("🧠 Training re-ranking model ...")
        results = train_model(X, y, model_path=path)

        logger.info("✅ Pipeline complete: %s", results)
        return results

    finally:
        await close_db_pool()


def main():
    parser = argparse.ArgumentParser(description="Offline training pipeline for re-ranking model")
    parser.add_argument("--dry-run", action="store_true", help="Only extract data, don't train")
    parser.add_argument("--model-path", type=str, default=None, help="Path to save the model")

    args = parser.parse_args()

    result = asyncio.run(run_pipeline(
        dry_run=args.dry_run,
        model_path=args.model_path,
    ))

    logger.info("Result: %s", result)
    sys.exit(0)


if __name__ == "__main__":
    main()
