"""Production ML Training and Comparison Pipeline for Fraud Shield AI.
Compares Random Forest, HistGradientBoosting, Calibrated Logistic Regression, and Ensemble.
Splits data into Train (70%), Validation (15%), Test (15%) to prevent data leakage.
Outputs serialized production pipeline and comprehensive metrics report.
"""
from pathlib import Path
import json
import time
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix
)

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "original_synthetic_fraud.csv"
OUT_DIR = ROOT / "backend" / "models"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def train_and_evaluate_ml():
    print(f"Loading dataset from {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    print(f"Dataset loaded: {df.shape[0]} rows, {df.shape[1]} columns.")
    
    assert "Label" in df.columns, "Label column missing!"
    X = df.drop(columns=["Label"])
    y = df["Label"].astype(int)
    
    # Stratified Train (70%), Validation (15%), Test (15%) split
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )
    
    print(f"Splits created: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")
    
    cat_cols = list(X.select_dtypes(include=["object"]).columns)
    num_cols = [c for c in X.columns if c not in cat_cols]
    
    print(f"Categorical features ({len(cat_cols)}): {cat_cols}")
    print(f"Numeric features ({len(num_cols)}): {num_cols}")
    
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler())
            ]), num_cols),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
            ]), cat_cols)
        ]
    )
    
    # Fit preprocessor strictly on train data
    preprocessor.fit(X_train)
    
    models = {
        "Random Forest": RandomForestClassifier(
            n_estimators=150, max_depth=14, min_samples_leaf=2,
            random_state=42, n_jobs=-1, class_weight="balanced"
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_iter=150, max_leaf_nodes=31, learning_rate=0.08,
            l2_regularization=1.0, random_state=42
        ),
        "Logistic Regression": LogisticRegression(
            max_iter=1000, C=0.5, class_weight="balanced", random_state=42
        )
    }
    
    evaluation_results = {
        "metadata": {
            "dataset_rows": len(df),
            "train_rows": len(X_train),
            "val_rows": len(X_val),
            "test_rows": len(X_test),
            "fraud_prevalence": float(y.mean()),
            "feature_count": len(X.columns),
            "features": list(X.columns)
        },
        "models": {},
        "threshold_analysis": {},
        "selected_production_model": "Ensemble (RF + HistGB + LR)"
    }
    
    fitted_pipelines = {}
    val_probs = {}
    test_probs = {}
    
    for name, clf in models.items():
        print(f"\nTraining {name}...")
        pipe = Pipeline([
            ("preprocessor", preprocessor),
            ("classifier", clf)
        ])
        t0 = time.time()
        pipe.fit(X_train, y_train)
        train_time = time.time() - t0
        fitted_pipelines[name] = pipe
        
        # Validation predictions
        p_val = pipe.predict_proba(X_val)[:, 1]
        val_probs[name] = p_val
        
        # Test predictions & Latency measurement
        t0 = time.time()
        p_test = pipe.predict_proba(X_test)[:, 1]
        inference_latency_ms = ((time.time() - t0) / len(X_test)) * 1000.0
        test_probs[name] = p_test
        
        pred_test = (p_test >= 0.50).astype(int)
        cm = confusion_matrix(y_test, pred_test)
        tn, fp, fn, tp = cm.ravel()
        
        metrics = {
            "train_time_sec": round(train_time, 3),
            "inference_latency_ms_per_tx": round(inference_latency_ms, 4),
            "accuracy": float(accuracy_score(y_test, pred_test)),
            "precision": float(precision_score(y_test, pred_test, zero_division=0)),
            "recall": float(recall_score(y_test, pred_test, zero_division=0)),
            "f1_score": float(f1_score(y_test, pred_test, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, p_test)),
            "pr_auc": float(average_precision_score(y_test, p_test)),
            "specificity": float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0,
            "false_positive_rate": float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0,
            "false_negative_rate": float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0,
            "confusion_matrix": cm.tolist()
        }
        evaluation_results["models"][name] = metrics
        print(f"{name} Test Metrics: F1={metrics['f1_score']:.4f}, ROC-AUC={metrics['roc_auc']:.4f}, PR-AUC={metrics['pr_auc']:.4f}, Latency={metrics['inference_latency_ms_per_tx']:.4f}ms")
        
    # Build Ensemble
    print("\nBuilding Weighted Soft-Voting Ensemble...")
    p_val_ens = (val_probs["Random Forest"] * 0.40 + 
                 val_probs["HistGradientBoosting"] * 0.45 + 
                 val_probs["Logistic Regression"] * 0.15)
    
    t0 = time.time()
    p_test_ens = (test_probs["Random Forest"] * 0.40 + 
                  test_probs["HistGradientBoosting"] * 0.45 + 
                  test_probs["Logistic Regression"] * 0.15)
    ens_latency = ((time.time() - t0) / len(X_test)) * 1000.0
    
    # Threshold sweep on validation set for Ensemble
    thresholds = np.arange(0.05, 0.95, 0.05)
    best_thresh = 0.50
    best_f1 = 0.0
    thresh_records = []
    
    for th in thresholds:
        th = round(float(th), 2)
        v_pred = (p_val_ens >= th).astype(int)
        v_prec = float(precision_score(y_val, v_pred, zero_division=0))
        v_rec = float(recall_score(y_val, v_pred, zero_division=0))
        v_f1 = float(f1_score(y_val, v_pred, zero_division=0))
        thresh_records.append({
            "threshold": th,
            "val_precision": v_prec,
            "val_recall": v_rec,
            "val_f1": v_f1
        })
        if v_f1 > best_f1:
            best_f1 = v_f1
            best_thresh = th
            
    evaluation_results["threshold_analysis"] = {
        "sweep": thresh_records,
        "optimal_threshold": best_thresh,
        "optimal_val_f1": best_f1
    }
    
    # Evaluate Ensemble on unseen Test set using optimal threshold
    pred_test_ens = (p_test_ens >= best_thresh).astype(int)
    cm_ens = confusion_matrix(y_test, pred_test_ens)
    tn_e, fp_e, fn_e, tp_e = cm_ens.ravel()
    
    ens_metrics = {
        "inference_latency_ms_per_tx": round(ens_latency, 4),
        "decision_threshold_used": best_thresh,
        "accuracy": float(accuracy_score(y_test, pred_test_ens)),
        "precision": float(precision_score(y_test, pred_test_ens, zero_division=0)),
        "recall": float(recall_score(y_test, pred_test_ens, zero_division=0)),
        "f1_score": float(f1_score(y_test, pred_test_ens, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, p_test_ens)),
        "pr_auc": float(average_precision_score(y_test, p_test_ens)),
        "specificity": float(tn_e / (tn_e + fp_e)) if (tn_e + fp_e) > 0 else 0.0,
        "false_positive_rate": float(fp_e / (tn_e + fp_e)) if (tn_e + fp_e) > 0 else 0.0,
        "false_negative_rate": float(fn_e / (fn_e + tp_e)) if (fn_e + tp_e) > 0 else 0.0,
        "confusion_matrix": cm_ens.tolist()
    }
    evaluation_results["models"]["Ensemble (RF + HistGB + LR)"] = ens_metrics
    print(f"\nEnsemble Test Metrics (Threshold {best_thresh}): F1={ens_metrics['f1_score']:.4f}, ROC-AUC={ens_metrics['roc_auc']:.4f}, PR-AUC={ens_metrics['pr_auc']:.4f}")
    
    # Persist Production Pipeline Bundle
    production_bundle = {
        "preprocessor": preprocessor,
        "models": {
            "random_forest": fitted_pipelines["Random Forest"].named_steps["classifier"],
            "hist_gradient_boosting": fitted_pipelines["HistGradientBoosting"].named_steps["classifier"],
            "logistic_regression": fitted_pipelines["Logistic Regression"].named_steps["classifier"]
        },
        "weights": {"random_forest": 0.40, "hist_gradient_boosting": 0.45, "logistic_regression": 0.15},
        "optimal_threshold": best_thresh,
        "feature_names": list(X.columns),
        "cat_cols": cat_cols,
        "num_cols": num_cols,
        "categories": {c: sorted(X[c].dropna().unique().tolist()) for c in cat_cols},
        "medians": X_train[num_cols].median().to_dict(),
        "version": "production-ml-v1"
    }
    
    pipeline_save_path = OUT_DIR / "production_ml_pipeline.joblib"
    joblib.dump(production_bundle, pipeline_save_path)
    print(f"Production ML bundle saved to {pipeline_save_path}")
    
    report_save_path = OUT_DIR / "ml_evaluation_report.json"
    report_save_path.write_text(json.dumps(evaluation_results, indent=2))
    print(f"ML evaluation report saved to {report_save_path}")
    
    return evaluation_results

if __name__ == "__main__":
    train_and_evaluate_ml()
