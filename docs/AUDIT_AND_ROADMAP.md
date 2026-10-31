# Original project audit and upgrade plan

- Original archive contains two notebooks: `DataSetGeneratorUSingNumpy.ipynb` and `FraudDetectionUSingGAN.ipynb`, 20,000-row generated CSV, and `best_rf_model (1).pkl`.
- 20 features + `Label`, no nulls, exactly 10,000 class-0 and 10,000 class-1 samples.
- Original GAN notebook uses a generator/discriminator to create synthetic vectors; its final prediction component is Random Forest. A GAN generator is not a deployed fraud detector.
- Original notebook applies MinMaxScaler before splitting, causing preprocessing leakage.
- v3 training fits preprocessing within a Pipeline after splitting; model and metrics are saved.
- v3 random split still cannot verify generalization across users or time, since source has neither account IDs nor timestamps.
- Perfect test metrics indicate synthetic label shortcuts / easy class separation; do not claim real-world accuracy.
- v3 uses rule-based sandbox decisions instead of feeding incomplete fields to the 20-feature ML model.
- Persistent transaction storage and WebSocket updates implemented; high-risk review API protected by a local admin key.
- QR parser is a syntax check, not QR image scanning, bank verification, or a guarantee against scams.

## Future development to reach deployment readiness

1. Get representative permissioned data and define privacy/retention policy.
2. Match feature extraction between simulator and model, add genuine temporal/user histories.
3. Compare RF, XGBoost, Isolation Forest and GAN augmentation with untouched temporal test data.
4. Add SHAP explanations for actual ML predictions and assess stability/fairness.
5. Implement real user authentication, role-based access, audit logs and rate limits.
6. Add migrations, production WebSocket authentication, Redis/event queue and monitoring.
7. Add automated browser E2E tests, CI/CD, threat modeling and security reviews.
8. Never connect to payment rails without an authorized partner and required compliance work.
