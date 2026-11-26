# IEEE-CIS Benchmark Integration Plan

## Purpose

Use IEEE-CIS as a separate, real-world e-commerce fraud benchmark for the ML Research area. Keep the existing synthetic UPI dataset for the UPI Sandbox and UI demonstrations. Do not merge the two datasets or describe IEEE-CIS scores as UPI detection performance.

## Access and current status

The IEEE-CIS competition data is not present in this workspace. Kaggle requires a signed-in account and acceptance of the competition rules before the files can be downloaded. The competition data is subject to those rules and must stay local; this repository ignores the raw and processed data folders.

Kaggle lists the training files as `train_transaction.csv` and `train_identity.csv`. They join on `TransactionID`; some transactions have no identity row. `TransactionDT` is a relative time offset, not a calendar timestamp. See the [competition data page](https://www.kaggle.com/competitions/ieee-fraud-detection/data) and [competition rules](https://www.kaggle.com/competitions/ieee-fraud-detection/rules).

When the files are available, place only the labeled training files here:

```text
data/ieee_cis/raw/train_transaction.csv
data/ieee_cis/raw/train_identity.csv
```

The unlabeled Kaggle test files are not needed to calculate accuracy, precision, recall, F1, or a confusion matrix, so the first benchmark run will not use them.

## Planned workflow

1. **Validate the files.** Check required columns, unique transaction IDs, fraud labels, row counts, missingness, and the identity-table join rate. Record class prevalence before training.
2. **Join safely.** Left-join identity data onto labeled transactions by `TransactionID`. Keep a single row per transaction and exclude the ID itself from model inputs.
3. **Split by time.** Sort by `TransactionDT` and create chronological train, validation, and final holdout periods. Fit imputation, category handling, scaling, and threshold selection on training/validation only. Do not tune on the final holdout.
4. **Train a separate benchmark.** Start with a reproducible baseline that can handle the dataset's categorical, numeric, and missing values. Keep its feature schema, model bundle, and metrics separate from the current UPI model artifacts.
5. **Report meaningful metrics.** On the untouched holdout, show fraud prevalence, accuracy, precision, recall, F1, PR-AUC, ROC-AUC, the validation-selected decision threshold, and confusion matrix. State clearly that the benchmark measures e-commerce fraud data.
6. **Show results separately.** Add an IEEE-CIS comparison card or report in ML Research only after a benchmark run succeeds. Label it “IEEE-CIS e-commerce benchmark” and keep the UPI Sandbox probability and model unchanged.

## What it can and cannot support

IEEE-CIS can provide an external test of the project's fraud-modeling and evaluation workflow. Its fields cover online transactions and identity/device information, but they do not provide UPI-specific flow, Indian UPI PSP, merchant-category, or state fields in the same form as the sandbox. Its scores therefore cannot establish UPI-specific performance or be used directly to score UPI Sandbox transactions.

For a future UPI-trained model, use authorized, de-identified UPI records with confirmed fraud outcomes and a matching feature schema. Do not infer fraud labels from the sandbox risk score, model prediction, or transaction amount.

## Next required input

After accepting Kaggle's competition rules, provide the two labeled training CSVs in `data/ieee_cis/raw/`. Then build and validate the dedicated preparation/training pipeline and decide how its separate metrics should appear in ML Research.
