"""Build a research-only evaluation report from the labeled source dataset.

Unlike train_models.py, this script never writes or replaces a model used by
the running application. It creates a reproducible comparison report only.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "2")

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    from .dataset_utils import load_labeled_training_data
except ImportError:
    from dataset_utils import load_labeled_training_data


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "original_synthetic_fraud.csv"
OUT_PATH = ROOT / "backend" / "models" / "dataset_research_metrics.json"
RANDOM_STATE = 42


def _downsample_curve(x_values, y_values, max_points: int = 121):
    if len(x_values) <= max_points:
        indices = np.arange(len(x_values))
    else:
        indices = np.linspace(0, len(x_values) - 1, max_points, dtype=int)
    return [
        [round(float(x_values[i]), 6), round(float(y_values[i]), 6)]
        for i in indices
    ]


def _make_pipeline(classifier, numeric_columns, categorical_columns):
    transformers = []
    if numeric_columns:
        numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
        if isinstance(classifier, LogisticRegression):
            numeric_steps.append(("scaler", StandardScaler()))
        transformers.append(("numeric", Pipeline(numeric_steps), numeric_columns))
    if categorical_columns:
        categorical = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ])
        transformers.append(("categorical", categorical, categorical_columns))

    preprocessing = ColumnTransformer(transformers=transformers, remainder="drop")
    return Pipeline([("preprocessor", preprocessing), ("classifier", classifier)])


def _select_threshold(y_true, probabilities):
    # Select only on validation data. Prefer the threshold closest to 0.50 on ties.
    thresholds = np.linspace(0.05, 0.95, 19)
    records = []
    best_key = (-1.0, -1.0, -1.0)
    best_threshold = 0.5
    for threshold in thresholds:
        predictions = (probabilities >= threshold).astype(int)
        precision = float(precision_score(y_true, predictions, zero_division=0))
        recall = float(recall_score(y_true, predictions, zero_division=0))
        f1 = float(f1_score(y_true, predictions, zero_division=0))
        records.append({
            "threshold": round(float(threshold), 2),
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "flagged_count": int(predictions.sum()),
        })
        key = (f1, precision, -abs(float(threshold) - 0.5))
        if key > best_key:
            best_key = key
            best_threshold = float(threshold)
    return best_threshold, records


def evaluate_dataset():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH}")

    all_rows, labeled, features, labels = load_labeled_training_data(DATA_PATH)
    labels = labels.astype(int)
    if set(labels.unique()) != {0, 1}:
        raise ValueError("The labeled dataset must contain both Label 0 and Label 1.")

    # This source has no account IDs or timestamps. Use a stratified split and
    # state that limitation rather than implying chronological validation.
    x_train, x_remainder, y_train, y_remainder = train_test_split(
        features, labels, test_size=0.30, random_state=RANDOM_STATE, stratify=labels
    )
    x_validation, x_test, y_validation, y_test = train_test_split(
        x_remainder, y_remainder, test_size=0.50, random_state=RANDOM_STATE, stratify=y_remainder
    )

    categorical_columns = list(features.select_dtypes(include=["object", "category"]).columns)
    numeric_columns = [column for column in features.columns if column not in categorical_columns]
    classifiers = {
        "Random Forest": RandomForestClassifier(
            n_estimators=140, max_depth=14, min_samples_leaf=2,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "Extra Trees": ExtraTreesClassifier(
            n_estimators=120, max_depth=16, min_samples_leaf=2,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "Histogram Gradient Boosting": HistGradientBoostingClassifier(
            max_iter=140, max_leaf_nodes=31, learning_rate=0.08,
            l2_regularization=1.0, random_state=RANDOM_STATE,
        ),
        "Logistic Regression": LogisticRegression(
            max_iter=1500, C=0.5, class_weight="balanced", random_state=RANDOM_STATE, solver="liblinear",
        ),
    }

    evaluated = {}
    validation_scores = {}
    test_scores = {}
    for name, classifier in classifiers.items():
        pipeline = _make_pipeline(classifier, numeric_columns, categorical_columns)
        started = time.perf_counter()
        pipeline.fit(x_train, y_train)
        train_seconds = time.perf_counter() - started
        validation_scores[name] = pipeline.predict_proba(x_validation)[:, 1]
        started = time.perf_counter()
        test_scores[name] = pipeline.predict_proba(x_test)[:, 1]
        latency_ms = (time.perf_counter() - started) * 1000 / max(1, len(x_test))

        threshold, sweep = _select_threshold(y_validation, validation_scores[name])
        selected_validation_metrics = min(
            sweep, key=lambda row: abs(row["threshold"] - threshold)
        )
        predictions = (test_scores[name] >= threshold).astype(int)
        matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
        report = classification_report(
            y_test, predictions, labels=[0, 1], target_names=["Legitimate", "Fraud"],
            output_dict=True, zero_division=0,
        )
        fpr, tpr, _ = roc_curve(y_test, test_scores[name])
        pr_precision, pr_recall, _ = precision_recall_curve(y_test, test_scores[name])
        evaluated[name] = {
            "metrics": {
                "threshold": threshold,
                "accuracy": float(accuracy_score(y_test, predictions)),
                "precision": float(precision_score(y_test, predictions, zero_division=0)),
                "recall": float(recall_score(y_test, predictions, zero_division=0)),
                "f1": float(f1_score(y_test, predictions, zero_division=0)),
                "roc_auc": float(roc_auc_score(y_test, test_scores[name])),
                "pr_auc": float(average_precision_score(y_test, test_scores[name])),
                "confusion_matrix": matrix.tolist(),
                "train_seconds": round(train_seconds, 3),
                "inference_ms_per_row": round(latency_ms, 5),
                "validation_precision_at_threshold": selected_validation_metrics["precision"],
                "validation_recall_at_threshold": selected_validation_metrics["recall"],
                "validation_f1_at_threshold": selected_validation_metrics["f1"],
            },
            "classification_report": report,
            "threshold_sweep": sweep,
            "roc_curve": _downsample_curve(fpr, tpr),
            "pr_curve": _downsample_curve(pr_recall, pr_precision),
        }

    selected_model = max(
        evaluated,
        key=lambda name: (
            evaluated[name]["metrics"]["validation_f1_at_threshold"],
            evaluated[name]["metrics"]["validation_precision_at_threshold"],
            evaluated[name]["metrics"]["validation_recall_at_threshold"],
        ),
    )
    y_series = labels
    metadata = {
        "source_file": "data/original_synthetic_fraud.csv",
        "dataset_type": "Synthetic labeled research dataset",
        "labeled_rows": int(len(labeled)),
        "unlabeled_rows_excluded": int(len(all_rows) - len(labeled)),
        "train_rows": int(len(x_train)),
        "validation_rows": int(len(x_validation)),
        "test_rows": int(len(x_test)),
        "fraud_prevalence": float(y_test.mean()),
        "majority_class_baseline_accuracy": float(max(y_series.value_counts(normalize=True))),
        "feature_count": int(features.shape[1]),
        "features": list(features.columns),
        "split": "Stratified random 70/15/15; source data has no account IDs or reliable event timestamps.",
        "random_state": RANDOM_STATE,
    }
    result = {
        "available": True,
        "metadata": metadata,
        "selected_model": selected_model,
        "models": evaluated,
        "warning": (
            "All labeled rows in this source are synthetic. These metrics measure separation of generated labels only; "
            "they are not evidence of real-world or UPI fraud performance. The source has no timestamps/account IDs, "
            "so this report uses a stratified random split rather than a temporal or customer-held-out evaluation."
        ),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    report = evaluate_dataset()
    print(json.dumps({
        "output": str(OUT_PATH),
        "selected_model": report["selected_model"],
        "models": {name: values["metrics"] for name, values in report["models"].items()},
        "metadata": report["metadata"],
    }, indent=2))
