"""Train an illustrative classifier on generated sandbox scenarios.

Synthetic labels are NOT verified fraud outcomes. This is for software integration
and academic demonstration only. Never claim real-world UPI detection performance.
"""
from pathlib import Path
import json
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, average_precision_score, confusion_matrix, precision_recall_curve, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'backend' / 'models'
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20261029)


def _downsample_curve(x_values, y_values, max_points=121):
    if len(x_values) <= max_points:
        indices = np.arange(len(x_values))
    else:
        indices = np.linspace(0, len(x_values) - 1, max_points, dtype=int)
    return [
        [round(float(x_values[index]), 6), round(float(y_values[index]), 6)]
        for index in indices
    ]


N = 16000
# Features match the frontend payment form exactly; use the same order at inference.
typical = RNG.uniform(200, 20000, N)
ratio = RNG.lognormal(mean=.45, sigma=1.2, size=N)
amount = np.clip(typical * ratio, 1, 1000000)
recent = RNG.poisson(2.5, N).clip(0, 100)
hour = RNG.integers(0, 24, N)
new = RNG.binomial(1, .28, N)
X = np.column_stack([amount, typical, recent, hour, new, amount / typical])
# Noisy demonstration labels from a deliberately transparent synthetic scenario.
# Random noise prevents a trivially perfect deterministic label mapping.
logit = -3.8 + 1.35 * (ratio > 5) + 1.0 * new + .95 * (recent >= 5) + .6 * (hour < 5) + .4 * (ratio > 2)
prob = 1 / (1 + np.exp(-logit))
y = RNG.binomial(1, prob)
X_train_val, Xte, y_train_val, yte = train_test_split(X, y, test_size=.15, random_state=42, stratify=y)
Xtr, Xval, ytr, yval = train_test_split(X_train_val, y_train_val, test_size=(.15 / .85), random_state=43, stratify=y_train_val)
model = RandomForestClassifier(n_estimators=160, min_samples_leaf=12, max_depth=10, n_jobs=-1, random_state=42)
model.fit(Xtr, ytr)
validation_scores = model.predict_proba(Xval)[:, 1]
val_precision, val_recall, thresholds = precision_recall_curve(yval, validation_scores)
val_f1 = 2 * val_precision[:-1] * val_recall[:-1] / (val_precision[:-1] + val_recall[:-1] + 1e-12)
best_threshold_index = int(np.argmax(val_f1))
threshold = float(thresholds[best_threshold_index])
scores = model.predict_proba(Xte)[:, 1]
pred = (scores >= threshold).astype(int)
fpr, tpr, _ = roc_curve(yte, scores)
pr_precision, pr_recall, _ = precision_recall_curve(yte, scores)
threshold_sweep = []
for sweep_threshold in np.linspace(.05, .95, 91):
    sweep_predictions = (validation_scores >= sweep_threshold).astype(int)
    sweep_precision = precision_score(yval, sweep_predictions, zero_division=0)
    sweep_recall = recall_score(yval, sweep_predictions, zero_division=0)
    threshold_sweep.append({
        'threshold': round(float(sweep_threshold), 2),
        'precision': float(sweep_precision),
        'recall': float(sweep_recall),
        'f1': float(f1_score(yval, sweep_predictions, zero_division=0)),
        'flagged_count': int(sweep_predictions.sum()),
    })
joblib.dump({'model':model, 'features':['amount','typical_amount','recent_count','hour','new_recipient','amount_to_typical_ratio'], 'version':'sandbox-ml-v1'}, OUT / 'sandbox_pipeline.joblib')
metrics = {
    'dataset': 'Generated sandbox scenarios',
    'model': 'Random Forest',
    'warning': 'These are metrics against generated labels, not verified UPI fraud outcomes. They demonstrate the evaluation pipeline only and do not establish real-world detection performance.',
    'train_rows': len(Xtr),
    'validation_rows': len(Xval),
    'test_rows': len(Xte),
    'fraud_prevalence': float(yte.mean()),
    'majority_class_baseline_accuracy': float(max((yte == 0).mean(), (yte == 1).mean())),
    'accuracy': float(accuracy_score(yte, pred)),
    'precision': float(precision_score(yte, pred, zero_division=0)),
    'recall': float(recall_score(yte, pred, zero_division=0)),
    'f1': float(f1_score(yte, pred, zero_division=0)),
    'pr_auc': float(average_precision_score(yte, scores)),
    'roc_auc': float(roc_auc_score(yte, scores)),
    'confusion_matrix': confusion_matrix(yte, pred).tolist(),
    'roc_curve': _downsample_curve(fpr, tpr),
    'pr_curve': _downsample_curve(pr_recall[::-1], pr_precision[::-1]),
    'threshold_sweep': threshold_sweep,
    'threshold': threshold,
    'validation_f1_at_threshold': float(val_f1[best_threshold_index]),
    'split': 'Stratified 70/15/15 train/validation/test split; random_state=42/43',
    'features': ['amount', 'typical_amount', 'recent_count', 'hour', 'new_recipient', 'amount_to_typical_ratio']
}
(OUT / 'sandbox_metrics.json').write_text(json.dumps(metrics, indent=2))
print(json.dumps(metrics,indent=2))
