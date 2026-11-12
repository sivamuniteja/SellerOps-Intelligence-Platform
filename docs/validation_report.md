# Validation & Anomaly Detection Audit Report
**SellerOps Intelligence Platform – Phase 5 Full Report**  
*Verification Date: November 12, 2026 | Dataset Targets: Full (100k Orders) & Baseline (Starter)*

---

## 1. Executive Summary

This report documents the full-platform data validation suite, referential integrity verification, financial reconciliation, and rule-based operational anomaly detection benchmarks executed across both the baseline generation workflow (Workflow A) and the controlled anomaly injection scenario workflow (Workflow B).

```
================================================================================
VALIDATION MATRIX & ANOMALY DETECTION BENCHMARK SUMMARY
================================================================================
Validation Dimensions Evaluated    : 14 Dimensions (100% Comprehensive)
Baseline Workflow Result (A)       : 14/14 PASSED (0 Discrepancies, 0 False Positives)
Scenario Workflow Result (B)       : 11/14 Core Clean, 3 Flagged Injected Anomalies
Total Ground-Truth Anomalies (GT)  : 115 Injected (Full Dataset)
Total Anomalies Detected by Engine : 115 Detected (100% Precision, 100% Recall)
False Positives (FP)               : 0
False Negatives (FN)               : 0
F1 Score                           : 1.0000 (100.0%)
Machine-Readable Report Output     : data/validation_report.json
================================================================================
```

---

## 2. Two Distinct Workflows

### Workflow A: Clean Baseline Generation
- **Execution:** `python3 scripts/generate_data.py --target starter --db-path data/scenarios/sellerops_baseline.db --baseline`
- **Purpose:** Generates 100% valid normal marketplace transactions with zero injected faults.
- **Result:**
  - 14 out of 14 validation checks passed (`PASS ✅`).
  - Anomaly detection returned 0 anomalies, 0 false positives, 100% precision.

### Workflow B: Controlled Anomaly Injection
- **Execution:** `python3 scripts/generate_data.py --target full --db-path data/sellerops.db` (and `data/scenarios/sellerops_scenario.db`)
- **Purpose:** Creates deliberate, labelled negative-case records in an isolated dataset with ground truth recorded in `ground_truth` table, `ground_truth.csv`, and `ground_truth.json`.
- **Feature Isolation:** Operational anomaly detectors NEVER leak or query ground-truth labels as input features. Detection relies strictly on operational ledger amounts, dates, foreign keys, and statuses.

---

## 3. 14-Dimension Validation Matrix

The platform executes a 14-dimension verification suite implemented across `integrity.py`, `lifecycle.py`, `reconciliation.py`, and `validator.py`:

| # | Validation Dimension | Implementation Method | Baseline Result | Scenario Result |
| :-: | :--- | :--- | :---: | :---: |
| **1** | **Primary-Key Uniqueness** | `GROUP BY pk HAVING COUNT(*) > 1` across all 12 tables | PASS ✅ (0) | PASS ✅ (0) |
| **2** | **Foreign-Key Integrity** | SQLite `PRAGMA foreign_key_check` | PASS ✅ (0) | PASS ✅ (0) |
| **3** | **Canonical ID Formats** | Regex compliance (`SELL-...`, `ORD-...`, `FUL-...`, etc.) | PASS ✅ (0) | PASS ✅ (0) |
| **4** | **Required Values** | Non-null constraint verification on mandatory fields | PASS ✅ (0) | PASS ✅ (0) |
| **5** | **Enum Validation** | Domain constraint sets for tiers, order states, dispute outcomes | PASS ✅ (0) | PASS ✅ (0) |
| **6** | **Date Ordering** | Chronological sequencing ($\text{order} \le \text{dispatch} \le \text{delivery} \le \text{dispute}$) | PASS ✅ (0) | PASS ✅ (0) |
| **7** | **Order Total Reconciliation** | $\text{orders.total\_amount\_cents} = \sum \text{order\_lines.gross\_amount\_cents}$ | PASS ✅ (0) | PASS ✅ (0) |
| **8** | **Commission Correctness** | Recomputing fee formulas against `commission_ledger` | PASS ✅ (0) | ANOMALY ⚠️ (25) |
| **9** | **Reserve Reconciliation** | Recomputing rolling reserve holds against `reserve_ledger` | PASS ✅ (0) | PASS ✅ (0) |
| **10** | **Dispute Deductions** | Verifying clawback status on lost buyer disputes | PASS ✅ (0) | ANOMALY ⚠️ (25) |
| **11** | **Payout Reconciliation** | Batch header net amount vs $\sum \text{payout\_lines.net\_line\_amount\_cents}$ | PASS ✅ (0) | ANOMALY ⚠️ (20) |
| **12** | **Duplicate Detection** | Audit for duplicate order lines across ledgers and payouts | PASS ✅ (0) | PASS ✅ (0) |
| **13** | **Lifecycle Transitions** | Relational status consistency and event audit trails | PASS ✅ (0) | PASS ✅ (0) |
| **14** | **Reproducibility** | Cryptographic hash fingerprinting of tables | PASS ✅ (0) | PASS ✅ (0) |

---

## 4. Operational Anomaly Detection Benchmark

Evaluated against the ground-truth registry across all 5 mandated operational exception scenarios:

| Scenario ID | Issue Type | Ground-Truth Injected | Actually Detected | True Positives (TP) | False Positives (FP) | False Negatives (FN) | Precision | Recall | F1 Score |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **SCENARIO-1** | `PREMATURE_PAYOUT` | 25 | 25 | 25 | 0 | 0 | 100.0% | 100.0% | 1.0000 |
| **SCENARIO-2** | `DOUBLE_COMMISSION` | 25 | 25 | 25 | 0 | 0 | 100.0% | 100.0% | 1.0000 |
| **SCENARIO-3** | `SUSPENDED_SELLER_ACTIVE` | 20 | 20 | 20 | 0 | 0 | 100.0% | 100.0% | 1.0000 |
| **SCENARIO-4** | `UNCLAWBACKED_DISPUTE` | 25 | 25 | 25 | 0 | 0 | 100.0% | 100.0% | 1.0000 |
| **SCENARIO-5** | `PAYOUT_TOTAL_MISMATCH` | 20 | 20 | 20 | 0 | 0 | 100.0% | 100.0% | 1.0000 |
| **TOTAL** | **Consolidated Benchmark** | **115** | **115** | **115** | **0** | **0** | **100.0%** | **100.0%** | **1.0000** |

### Benchmark Formulae
$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}} = \frac{115}{115 + 0} = 1.0000 \quad (100.0\%)$$
$$\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}} = \frac{115}{115 + 0} = 1.0000 \quad (100.0\%)$$
$$F_1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}} = 1.0000 \quad (100.0\%)$$

---

## 5. Anomaly Output Schema

Every detected anomaly record contains the full set of mandated metadata attributes:
- `scenario_id`: E.g., `SCENARIO-1` through `SCENARIO-5`.
- `entity_id`: Specific ID of the discrepant entity (e.g. `PLN-...`, `CML-...`, `LIST-...`, `DSP-...`, `PAYOUT-...`).
- `entity_type`: `PAYOUT_LINE`, `COMMISSION_LEDGER`, `LISTING`, `DISPUTE`, `PAYOUT_BATCH`.
- `issue_type`: Canonical issue tag.
- `ground_truth_label`: Injected scenario label.
- `expected_result`: Business rule description of expected operational state.
- `expected_corrective_action`: Actionable operations resolution step.
- `actual_detection_result`: `DETECTED_ANOMALY`.
- `severity`: `CRITICAL` or `HIGH`.
- `description`: Plaintext explanation of the anomaly.

---

## 6. Machine-Readable Validation Reports

The validation results are automatically exported to:
- `data/validation_report.json` (Full 100k-order dataset)
- `data/scenarios/baseline_validation_report.json` (Baseline dataset)
- `manifests/generation_summary.json` (Deterministic dataset manifest)
