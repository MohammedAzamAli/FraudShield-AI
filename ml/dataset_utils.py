"""Shared loading rules for the labeled synthetic fraud dataset.

UPI Sandbox examples are deliberately unlabeled until a valid outcome is known.
They stay in the CSV for schema coverage but must not enter model training or
held-out evaluation.
"""
from pathlib import Path

import pandas as pd


UPI_CONTEXT_COLUMNS = [
    "sender_upi",
    "recipient_upi",
    "channel",
    "transactions_last_24h",
    "average_amount_30d",
    "first_merchant_visit",
    "payment_service_provider",
    "merchant_category",
    "transaction_state",
    "device_os",
    "transaction_time",
    "screening_mode",
    "screening_cutoff",
    "device_is_new",
    "vpn_detected",
    "device_id",
]


def load_labeled_training_data(path: str | Path):
    """Return all rows, labeled rows, legacy model features, and labels."""
    all_rows = pd.read_csv(path, low_memory=False)
    if "Label" not in all_rows.columns:
        raise ValueError("Dataset must include a Label column.")

    labeled = all_rows.loc[all_rows["Label"].notna()].copy()
    if labeled.empty:
        raise ValueError("Dataset has no labeled rows to train or evaluate.")

    y = labeled["Label"].astype(int)
    excluded = ["Label", "Record Type", *UPI_CONTEXT_COLUMNS]
    X = labeled.drop(columns=excluded, errors="ignore")
    return all_rows, labeled, X, y
