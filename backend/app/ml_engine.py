"""Inference Engine for Production Machine Learning and Deep Learning.
Loads:
1. Ensemble ML Pipeline (Random Forest + HistGB + Logistic Regression)
2. PyTorch Deep Anomaly Autoencoder (Reconstruction error scoring)
3. PyTorch Temporal Sequence BiGRU (Behavioral sequence risk scoring)
"""
from pathlib import Path
import json
import time
import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from functools import lru_cache

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"

# Autoencoder Architecture matching training
class AnomalyAutoencoder(nn.Module):
    def __init__(self, input_dim: int, latent_dim: int = 4):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.BatchNorm1d(16),
            nn.LeakyReLU(0.1),
            nn.Linear(16, 8),
            nn.LeakyReLU(0.1),
            nn.Linear(8, latent_dim)
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 8),
            nn.LeakyReLU(0.1),
            nn.Linear(8, 16),
            nn.BatchNorm1d(16),
            nn.LeakyReLU(0.1),
            nn.Linear(16, input_dim)
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z)

# Sequence BiGRU matching training
class TemporalSequenceGRU(nn.Module):
    def __init__(self, feature_dim: int = 5, hidden_dim: int = 16):
        super().__init__()
        self.gru = nn.GRU(
            input_size=feature_dim,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.1
        )
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 2, 16),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        out, _ = self.gru(x)
        last_step = out[:, -1, :]
        prob = self.classifier(last_step)
        return prob.squeeze(-1)

class ProductionMLEngine:
    _instance = None

    def __init__(self):
        self.ml_bundle = None
        self.autoencoder = None
        self.ae_params = {}
        self.sequence_gru = None
        self.gru_params = {}
        self._loaded = False

    def ensure_loaded(self):
        if not self._loaded:
            self.load_artifacts()
            self._loaded = True

    def load_artifacts(self):
        # 1. Load ML Ensemble
        ml_path = MODELS_DIR / "production_ml_pipeline.joblib"
        if ml_path.exists():
            self.ml_bundle = joblib.load(ml_path)
            # Ensure single-threaded CPU inference to avoid loky process-pool hangs
            if "models" in self.ml_bundle and "random_forest" in self.ml_bundle["models"]:
                self.ml_bundle["models"]["random_forest"].n_jobs = 1
        else:
            print(f"Warning: {ml_path} not found. Train with ml/train_models.py")

        # 2. Load PyTorch Autoencoder
        ae_path = MODELS_DIR / "production_dl_autoencoder.pt"
        if ae_path.exists():
            checkpoint = torch.load(ae_path, map_location="cpu", weights_only=False)
            self.autoencoder = AnomalyAutoencoder(
                input_dim=checkpoint["input_dim"],
                latent_dim=checkpoint["latent_dim"]
            )
            self.autoencoder.load_state_dict(checkpoint["state_dict"])
            self.autoencoder.eval()
            self.ae_params = {
                "mean": checkpoint["baseline_mean"],
                "std": checkpoint["baseline_std"],
                "threshold": checkpoint["threshold"]
            }
        else:
            print(f"Warning: {ae_path} not found. Train with ml/train_deep_learning.py")

        # 3. Load PyTorch Sequence BiGRU
        gru_path = MODELS_DIR / "production_dl_sequence.pt"
        if gru_path.exists():
            checkpoint = torch.load(gru_path, map_location="cpu", weights_only=False)
            self.sequence_gru = TemporalSequenceGRU(
                feature_dim=checkpoint["feature_dim"],
                hidden_dim=checkpoint["hidden_dim"]
            )
            self.sequence_gru.load_state_dict(checkpoint["state_dict"])
            self.sequence_gru.eval()
            self.gru_params = {"threshold": checkpoint["threshold"]}
        else:
            print(f"Warning: {gru_path} not found. Train with ml/train_deep_learning.py")

    def predict_ml(self, features_df: pd.DataFrame) -> dict:
        """Runs the 3-model weighted ensemble and returns fraud probability."""
        self.ensure_loaded()
        if not self.ml_bundle:
            return {"probability": 0.05, "models": {}, "latency_ms": 0.0}

        preprocessor = self.ml_bundle["preprocessor"]
        models = self.ml_bundle["models"]
        weights = self.ml_bundle["weights"]

        t0 = time.time()
        X_trans = preprocessor.transform(features_df)

        p_rf = float(models["random_forest"].predict_proba(X_trans)[0, 1])
        p_gb = float(models["hist_gradient_boosting"].predict_proba(X_trans)[0, 1])
        p_lr = float(models["logistic_regression"].predict_proba(X_trans)[0, 1])

        p_ens = (p_rf * weights["random_forest"] +
                 p_gb * weights["hist_gradient_boosting"] +
                 p_lr * weights["logistic_regression"])

        latency_ms = (time.time() - t0) * 1000.0

        return {
            "ensemble_fraud_probability": round(p_ens, 4),
            "random_forest_prob": round(p_rf, 4),
            "hist_gradient_boosting_prob": round(p_gb, 4),
            "logistic_regression_prob": round(p_lr, 4),
            "optimal_threshold": self.ml_bundle["optimal_threshold"],
            "flagged": p_ens >= self.ml_bundle["optimal_threshold"],
            "inference_latency_ms": round(latency_ms, 3)
        }

    def predict_dl_anomaly(self, features_df: pd.DataFrame) -> dict:
        """Reconstruction error anomaly scoring using PyTorch Autoencoder."""
        self.ensure_loaded()
        if not self.autoencoder or not self.ml_bundle:
            return {"anomaly_score": 0.05, "reconstruction_mse": 0.01, "latency_ms": 0.0}

        preprocessor = self.ml_bundle["preprocessor"]
        t0 = time.time()
        X_trans = preprocessor.transform(features_df).astype(np.float32)

        with torch.no_grad():
            tensor_x = torch.tensor(X_trans)
            recon = self.autoencoder(tensor_x).numpy()
            mse = float(np.mean(np.square(X_trans - recon)))

        # Calibrate into [0, 1] anomaly score using trained baseline
        baseline_mean = self.ae_params["mean"]
        baseline_std = self.ae_params["std"]
        z = (mse - baseline_mean) / (3.0 * baseline_std)
        score = 1.0 / (1.0 + np.exp(-z))
        latency_ms = (time.time() - t0) * 1000.0

        return {
            "dl_anomaly_score": round(float(score), 4),
            "reconstruction_mse": round(mse, 5),
            "baseline_mean_mse": round(baseline_mean, 5),
            "flagged": score >= self.ae_params.get("threshold", 0.5),
            "inference_latency_ms": round(latency_ms, 3)
        }

    def predict_dl_sequence(self, sequence_window: np.ndarray) -> dict:
        """Evaluates customer temporal behavioral sequence using BiGRU."""
        self.ensure_loaded()
        # sequence_window shape: (1, seq_len=5, feature_dim=5)
        if not self.sequence_gru:
            return {"sequence_risk_score": 0.05, "latency_ms": 0.0}

        t0 = time.time()
        with torch.no_grad():
            tensor_seq = torch.tensor(sequence_window, dtype=torch.float32)
            prob = float(self.sequence_gru(tensor_seq).numpy()[0])
        latency_ms = (time.time() - t0) * 1000.0

        return {
            "dl_sequence_risk_score": round(prob, 4),
            "flagged": prob >= self.gru_params.get("threshold", 0.5),
            "inference_latency_ms": round(latency_ms, 3)
        }

@lru_cache(maxsize=1)
def get_ml_engine() -> ProductionMLEngine:
    return ProductionMLEngine()
