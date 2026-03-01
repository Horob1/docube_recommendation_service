"""
Model trainer for offline re-ranking model.

Trains a LightGBM (or fallback LogisticRegression) classifier
on positive (buy/bookmark) and negative (view-only) samples.
Saves the trained model to disk for the re-ranker to load.
"""

import logging
from pathlib import Path

import numpy as np
import joblib

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path("models/reranker.pkl")


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    model_path: Path = DEFAULT_MODEL_PATH,
    use_lightgbm: bool = True,
) -> dict:
    """
    Train a binary classifier for re-ranking.

    Args:
        X_train: Feature matrix (N, 6).
        y_train: Labels (1 = positive engagement, 0 = negative).
        model_path: Path to save the trained model.
        use_lightgbm: If True, use LightGBM; otherwise LogisticRegression.

    Returns:
        Training results dict with accuracy and model info.
    """
    if len(X_train) < 10:
        logger.warning("⚠️  Not enough training data (%d samples). Skipping.", len(X_train))
        return {"status": "skipped", "reason": "insufficient data", "samples": len(X_train)}

    # Split for evaluation
    from sklearn.model_selection import train_test_split
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=0.2, random_state=42, stratify=y_train,
    )

    if use_lightgbm:
        model, model_type = _train_lightgbm(X_tr, y_tr)
    else:
        model, model_type = _train_logreg(X_tr, y_tr)

    # Evaluate
    from sklearn.metrics import accuracy_score, roc_auc_score
    y_pred = model.predict(X_val)
    accuracy = accuracy_score(y_val, y_pred)

    try:
        y_prob = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, y_prob)
    except Exception:
        auc = None

    # Save model
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    results = {
        "status": "trained",
        "model_type": model_type,
        "model_path": str(model_path),
        "train_samples": len(X_tr),
        "val_samples": len(X_val),
        "accuracy": round(accuracy, 4),
        "auc": round(auc, 4) if auc else None,
    }

    logger.info("✅ Model trained: %s", results)
    return results


def _train_lightgbm(X: np.ndarray, y: np.ndarray):
    """Train a LightGBM classifier."""
    try:
        import lightgbm as lgb

        model = lgb.LGBMClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            num_leaves=31,
            min_child_samples=5,
            random_state=42,
            verbose=-1,
        )
        model.fit(X, y)
        return model, "LGBMClassifier"
    except ImportError:
        logger.warning("⚠️  LightGBM not available, falling back to LogisticRegression")
        return _train_logreg(X, y)


def _train_logreg(X: np.ndarray, y: np.ndarray):
    """Train a LogisticRegression classifier (fallback)."""
    from sklearn.linear_model import LogisticRegression

    model = LogisticRegression(
        max_iter=1000,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X, y)
    return model, "LogisticRegression"
