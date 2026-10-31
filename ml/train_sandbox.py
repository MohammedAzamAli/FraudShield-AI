"""Train an illustrative classifier on generated sandbox scenarios.

Synthetic labels are NOT verified fraud outcomes. This is for software integration
and academic demonstration only. Never claim real-world UPI detection performance.
"""
from pathlib import Path
import json
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score, confusion_matrix
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'backend' / 'models'
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20261029)
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
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=.25, random_state=42, stratify=y)
model = RandomForestClassifier(n_estimators=160, min_samples_leaf=12, max_depth=10, n_jobs=-1, random_state=42)
model.fit(Xtr, ytr)
scores = model.predict_proba(Xte)[:, 1]
pred = (scores >= .15).astype(int)
joblib.dump({'model':model, 'features':['amount','typical_amount','recent_count','hour','new_recipient','amount_to_typical_ratio'], 'version':'sandbox-ml-v1'}, OUT / 'sandbox_pipeline.joblib')
metrics = {'dataset':'generated sandbox scenarios','warning':'Synthetic labels are not verified UPI fraud. These metrics cannot establish real-world detection capability.', 'train_rows':len(Xtr), 'test_rows':len(Xte), 'fraud_prevalence':float(y.mean()), 'precision':float(precision_score(yte,pred,zero_division=0)), 'recall':float(recall_score(yte,pred,zero_division=0)), 'f1':float(f1_score(yte,pred,zero_division=0)), 'pr_auc':float(average_precision_score(yte,scores)), 'confusion_matrix':confusion_matrix(yte,pred).tolist(), 'threshold':.15}
(OUT / 'sandbox_metrics.json').write_text(json.dumps(metrics, indent=2))
print(json.dumps(metrics,indent=2))
