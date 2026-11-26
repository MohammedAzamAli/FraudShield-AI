"""Add clearly marked, unlabeled UPI Sandbox examples to the synthetic CSV.

The existing 20,000 labeled rows are kept intact. New sandbox examples have
blank Label cells; see dataset_utils.py, which keeps them out of model training
and evaluation until verified outcomes are supplied.
"""
import csv
import os
import random
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "original_synthetic_fraud.csv"
SAMPLE_COUNT = 128
SEED = 20261125

SANDBOX_COLUMNS = [
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
META_COLUMNS = ["Record Type"]
FLOW_OPTIONS = ["UPI_P2P", "UPI_P2M", "COLLECT_REQUEST", "QR_CODE"]
PROVIDERS = ["PhonePe", "Google Pay", "Paytm", "BHIM", "Amazon Pay", "Other"]
CATEGORIES = [
    "General", "Groceries", "Utilities", "Food and dining", "Travel", "Retail",
    "Donations", "Money Mule Account", "Phishing Collect", "Other",
]
STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Jammu and Kashmir",
    "Ladakh", "Puducherry",
]
DEVICE_SYSTEMS = ["Android", "iOS", "Web", "Unknown"]
SCREENING_MODES = ["high", "balanced", "low", "custom"]


def _cycled(values, index, step):
    return values[(index * step) % len(values)]


def _sandbox_rows(fieldnames):
    rng = random.Random(SEED)
    for index in range(SAMPLE_COUNT):
        row = {field: "" for field in fieldnames}
        amount = round(rng.uniform(50, 50000), 2)
        average = round(rng.uniform(200, 20000), 2)
        count_24h = rng.randint(0, 24)
        is_new_device = rng.random() < 0.28
        first_visit = rng.random() < 0.35
        vpn = rng.random() < 0.08
        minute_of_day = (index * 37 + rng.randrange(60)) % (24 * 60)
        hour, minute = divmod(minute_of_day, 60)
        mode = _cycled(SCREENING_MODES, index, 1)
        cutoff = {"high": 0.15, "balanced": 0.25, "low": 0.45}.get(
            mode, round(rng.uniform(0.05, 0.80), 2)
        )

        row.update({
            "Record Type": "upi_sandbox_example_unlabeled",
            "sender_upi": f"sandbox.user{index % 16 + 1:02d}@upi",
            "recipient_upi": f"sandbox.merchant{index + 1:04d}@upi",
            "channel": _cycled(FLOW_OPTIONS, index, 3),
            "transactions_last_24h": str(count_24h),
            "average_amount_30d": f"{average:.2f}",
            "first_merchant_visit": str(int(first_visit)),
            "payment_service_provider": _cycled(PROVIDERS, index * 5, 1),
            "merchant_category": _cycled(CATEGORIES, index * 3, 1),
            "transaction_state": _cycled(STATES, index * 5, 1),
            "device_os": _cycled(DEVICE_SYSTEMS, index * 3, 1),
            "transaction_time": f"{hour:02d}:{minute:02d}",
            "screening_mode": mode,
            "screening_cutoff": f"{cutoff:.2f}",
            "device_is_new": str(int(is_new_device)),
            "vpn_detected": str(int(vpn)),
            "device_id": f"DEV-SBX-{index + 1:04d}",
            # Existing source columns that have a clear equivalent.
            "Transaction Amount": f"{amount:.2f}",
            "Transaction Frequency": str(count_24h),
            "Device Fingerprinting": str(int(is_new_device)),
            "VPN or Proxy Usage": str(int(vpn)),
            "High-Risk Transaction Times": str(int(hour < 5)),
            "Normalized Transaction Amount": f"{amount / average:.6f}",
            # No verified fraud outcome exists for these examples.
            "Label": "",
        })
        yield row


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(DATA_PATH)

    raw = DATA_PATH.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    line_ending = "\r\n" if b"\r\n" in raw[:8192] else "\n"
    with DATA_PATH.open("r", newline="", encoding=encoding) as source:
        reader = csv.DictReader(source)
        original_fields = list(reader.fieldnames or [])
        if "Label" not in original_fields:
            raise ValueError("The source CSV must contain a Label column.")
        rows = list(reader)

    # On rerun, replace only this script's sample rows; preserve all other records.
    rows = [row for row in rows if row.get("Record Type") != "upi_sandbox_example_unlabeled"]
    original_label_counts = Counter(row.get("Label", "") for row in rows)
    for row in rows:
        if not row.get("Record Type"):
            row["Record Type"] = "historical_synthetic_labeled" if row.get("Label") else "historical_unlabeled"

    fieldnames = [field for field in original_fields if field != "Label"]
    for field in (*META_COLUMNS, *SANDBOX_COLUMNS):
        if field not in fieldnames:
            fieldnames.append(field)
    fieldnames.append("Label")

    # These inputs did not exist in the source records, so keep them blank there.
    for row in rows:
        for field in SANDBOX_COLUMNS:
            row.setdefault(field, "")
        row.setdefault("Record Type", "historical_synthetic_labeled" if row.get("Label") else "historical_unlabeled")

    examples = list(_sandbox_rows(fieldnames))
    output_rows = rows + examples
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", newline="", encoding=encoding, dir=DATA_PATH.parent,
            suffix=".tmp", delete=False,
        ) as destination:
            temp_name = destination.name
            writer = csv.DictWriter(destination, fieldnames=fieldnames, extrasaction="ignore", lineterminator=line_ending)
            writer.writeheader()
            writer.writerows(output_rows)

        with open(temp_name, "r", newline="", encoding=encoding) as check_file:
            check_rows = list(csv.DictReader(check_file))
        if len(check_rows) != len(output_rows):
            raise RuntimeError("CSV row-count check failed; source file was not replaced.")
        if Counter(row.get("Label", "") for row in check_rows if row.get("Record Type") != "upi_sandbox_example_unlabeled") != original_label_counts:
            raise RuntimeError("Existing labels changed; source file was not replaced.")
        if any(not all(row.get(field) not in (None, "") for field in SANDBOX_COLUMNS) or row.get("Label", "") for row in check_rows[-SAMPLE_COUNT:]):
            raise RuntimeError("Sandbox example completeness check failed; source file was not replaced.")

        os.replace(temp_name, DATA_PATH)
        temp_name = None
    finally:
        if temp_name and os.path.exists(temp_name):
            os.remove(temp_name)

    print(f"Updated {DATA_PATH}")
    print(f"Preserved {len(rows)} existing rows and their label counts: {dict(original_label_counts)}")
    print(f"Added {SAMPLE_COUNT} unlabeled UPI Sandbox examples and {len(META_COLUMNS) + len(SANDBOX_COLUMNS)} columns.")


if __name__ == "__main__":
    main()
