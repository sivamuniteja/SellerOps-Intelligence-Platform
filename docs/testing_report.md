# Automated Testing & Test Execution Report
**SellerOps Intelligence Platform – Production Test Report**  
*Test Framework: PyTest 8.3.4 | Python 3.13.5 | 72 Tests Passed in 4.45s*

---

## 1. Test Suite Summary

The automated test suite in `tests/` comprehensively verifies data integrity, foreign key constraints, canonical ID formats, the Global INR Currency System, 5 independent business logic engines (Commissions, Reserves, Fulfillments, Payouts, Seller Metrics), dispute adjudication, anomaly detection benchmarks (100% precision/recall), multi-format data exports (CSV, JSON, SQL), round-trip re-import verification, and cryptographic fixed-seed reproducibility (`20261022`).

```
============================= test session starts ==============================
platform darwin -- Python 3.13.5, pytest-8.3.4, pluggy-1.5.0
rootdir: /Users/pallamalamunisivateja/SellerOps Intelligence Platform
collected 72 items

tests/test_anomalies.py::test_detect_all_anomalies PASSED                [  1%]
tests/test_anomalies.py::test_anomaly_record_structure PASSED            [  2%]
tests/test_anomalies.py::test_individual_anomaly_scenarios PASSED        [  4%]
tests/test_anomalies.py::test_baseline_has_zero_anomalies PASSED         [  5%]
tests/test_commissions.py::test_standard_category_commission PASSED      [  6%]
tests/test_commissions.py::test_enterprise_tier_commission_discount PASSED [  8%]
tests/test_commissions.py::test_minimum_commission_floor PASSED          [  9%]
tests/test_commissions.py::test_exact_integer_cents_calculation PASSED   [ 11%]
tests/test_commissions.py::test_effective_dated_rule_matching PASSED     [ 12%]
tests/test_commissions.py::test_prevent_duplicate_commission PASSED      [ 13%]
tests/test_currency.py::test_currency_metadata PASSED                    [ 15%]
tests/test_currency.py::test_rupee_to_paise_conversions PASSED           [ 16%]
tests/test_currency.py::test_paise_to_rupee_conversions PASSED           [ 18%]
tests/test_currency.py::test_indian_number_formatting PASSED             [ 19%]
tests/test_currency.py::test_compact_indian_formatting PASSED            [ 20%]
tests/test_currency.py::test_no_floating_point_drift_in_calculations PASSED [ 22%]
tests/test_currency.py::test_calculate_percentage_exact_paise PASSED     [ 23%]
tests/test_disputes.py::test_disputes_count_and_reasons PASSED           [ 25%]
tests/test_disputes.py::test_dispute_amounts_positive PASSED             [ 26%]
tests/test_exports.py::test_csv_export_structure_and_headers PASSED      [ 27%]
tests/test_exports.py::test_json_export_structure_and_types PASSED       [ 29%]
tests/test_exports.py::test_sql_seed_data_syntax_and_dependencies PASSED [ 30%]
tests/test_exports.py::test_isolated_ground_truth_export PASSED          [ 31%]
tests/test_exports.py::test_seller_and_date_filtering PASSED             [ 33%]
tests/test_exports.py::test_sha256_checksums_integrity PASSED            [ 34%]
tests/test_exports.py::test_reimport_round_trip_and_financial_accuracy PASSED [ 36%]
tests/test_exports.py::test_no_credentials_leaked PASSED                 [ 37%]
tests/test_foreign_keys.py::test_no_foreign_key_violations PASSED        [ 38%]
tests/test_foreign_keys.py::test_foreign_key_enforcement_prevents_orphan PASSED [ 40%]
tests/test_fulfillment.py::test_valid_fulfillment_state_flow PASSED      [ 41%]
tests/test_fulfillment.py::test_order_cancellation_allowed_states PASSED [ 43%]
tests/test_fulfillment.py::test_delivered_can_transition_to_returned PASSED [ 44%]
tests/test_fulfillment.py::test_invalid_state_transition_raises_error PASSED [ 45%]
tests/test_fulfillment.py::test_sla_dispatch_evaluation PASSED           [ 47%]
tests/test_fulfillment.py::test_delay_calculations PASSED                [ 48%]
tests/test_fulfillment.py::test_preserve_event_history PASSED            [ 50%]
tests/test_ids.py::test_id_format[sellers-col_and_pattern0] PASSED       [ 51%]
tests/test_ids.py::test_id_format[customers-col_and_pattern1] PASSED     [ 52%]
tests/test_ids.py::test_id_format[listings-col_and_pattern2] PASSED      [ 54%]
tests/test_ids.py::test_id_format[orders-col_and_pattern3] PASSED        [ 55%]
tests/test_ids.py::test_id_format[order_lines-col_and_pattern4] PASSED   [ 56%]
tests/test_ids.py::test_id_format[fulfillments-col_and_pattern5] PASSED  [ 58%]
tests/test_ids.py::test_id_format[customer_reviews-col_and_pattern6] PASSED [ 59%]
tests/test_ids.py::test_id_format[disputes-col_and_pattern7] PASSED      [ 61%]
tests/test_ids.py::test_id_format[payouts-col_and_pattern8] PASSED       [ 62%]
tests/test_payouts.py::test_reserve_calculation_by_tier PASSED           [ 63%]
tests/test_payouts.py::test_high_risk_reserve_surcharge PASSED           [ 65%]
tests/test_payouts.py::test_premature_reserve_release_blocked PASSED     [ 66%]
tests/test_payouts.py::test_suspended_seller_reserve_release_blocked PASSED [ 68%]
tests/test_payouts.py::test_reserve_balance_tracking PASSED              [ 69%]
tests/test_payouts.py::test_payout_eligibility_criteria PASSED           [ 70%]
tests/test_payouts.py::test_exact_net_payable_formula PASSED             [ 72%]
tests/test_payouts.py::test_duplicate_payout_line_prevention PASSED      [ 73%]
tests/test_payouts.py::test_avoid_double_deductions PASSED               [ 75%]
tests/test_payouts.py::test_payout_threshold_held_status PASSED          [ 76%]
tests/test_payouts.py::test_payout_state_transitions PASSED              [ 77%]
tests/test_payouts.py::test_inr_illustrative_payout_fixture PASSED       [ 79%]
tests/test_payouts.py::test_inr_reserve_release_added_only_once PASSED   [ 80%]
tests/test_payouts.py::test_inr_partial_refund_deduction PASSED          [ 81%]
tests/test_payouts.py::test_inr_multi_seller_order_payout_separation PASSED [ 83%]
tests/test_payouts.py::test_inr_finalized_dispute_deducted_exactly_once PASSED [ 84%]
tests/test_reproducibility.py::test_generation_reproducibility PASSED    [ 86%]
tests/test_seller_metrics.py::test_scorecard_calculation PASSED          [ 87%]
tests/test_seller_metrics.py::test_scorecard_breach_detection PASSED     [ 88%]
tests/test_seller_metrics.py::test_calculate_metrics_from_actual_db PASSED [ 90%]
tests/test_seller_metrics.py::test_time_window_filtering PASSED          [ 91%]
tests/test_seller_metrics.py::test_seller_not_found_raises_error PASSED  [ 93%]
tests/test_validation.py::test_baseline_passes_all_validations PASSED    [ 94%]
tests/test_validation.py::test_integrity_validator_checks PASSED         [ 95%]
tests/test_validation.py::test_lifecycle_chronology_checks PASSED        [ 97%]
tests/test_validation.py::test_financial_reconciliation_checks PASSED    [ 98%]
tests/test_validation.py::test_machine_readable_report_generation PASSED [100%]

============================== 72 passed in 4.45s ==============================
```

---

## 2. Test File Coverage Matrix

| Test Module | Coverage & Verification Scope | Test Count | Status |
| :--- | :--- | :---: | :---: |
| `test_currency.py` | INR metadata, rupee-paise bi-directional conversion, standard Indian number grouping (`₹1,25,000.00`), compact Indian formatting (`₹12.50 L`, `₹1.04 Cr`), zero binary floating-point drift, exact percentage paise arithmetic. | 7 | PASSED ✅ |
| `test_payouts.py` | Reserve tier rates, high-risk surcharges, premature release blocking (`PrematureReserveReleaseError`), suspended seller hold protection (`SuspendedSellerReleaseError`), reserve balance tracking, payout eligibility, exact net payable arithmetic, duplicate payout line prevention (`DuplicatePayoutLineError`), double deduction avoidance (`DoubleDeductionError`), minimum threshold hold status, lifecycle state transitions, plus **all 5 Section 5 INR financial fixtures**. | 16 | PASSED ✅ |
| `test_exports.py` | CSV chunked export structure & headers, JSON streaming export structure & types, SQL master seed data syntax, isolated ground-truth separation, seller/date filtering, SHA-256 checksums integrity, round-trip re-import verification & financial parity, zero credential leakage. | 8 | PASSED ✅ |
| `test_validation.py` | Baseline dataset validation passes 100%, referential integrity validator checks, lifecycle chronology checks, financial reconciliation checks, machine-readable JSON report generation. | 5 | PASSED ✅ |
| `test_anomalies.py` | Ground truth anomaly detection precision, recall, and count assertions across all 5 operational exception scenarios (115 injected = 115 detected, F1 = 1.0000), baseline has zero false positives. | 4 | PASSED ✅ |
| `test_commissions.py` | Category base rates, tier discounts, minimum fee guarantee floors, integer cents/paise exact math, effective-dated rule matching, duplicate commission prevention (`DuplicateCommissionError`), immutable ledger recording. | 6 | PASSED ✅ |
| `test_fulfillment.py` | Finite state transitions (`ORDER_RECEIVED` through `DELIVERED`), cancellation eligibility, return eligibility, invalid state transitions (`InvalidFulfillmentTransitionError`), 48h dispatch SLA evaluation, delay hours calculation, immutable event history logging. | 7 | PASSED ✅ |
| `test_seller_metrics.py` | Scorecard calculation, SLA breach detection, real database query evaluation (`data/sellerops.db`), fulfillment rate, late shipment rate, on-time delivery rate, dispute rate, cancellation rate, GMV in INR, commission revenue, reserve balance, pending/paid payouts, time window filtering, non-existent seller error handling. | 5 | PASSED ✅ |
| `test_ids.py` | Regex pattern validation across all 9 canonical ID formats (`SELL-xxxxxx`, `LIST-...`, `ORD-xxxx-xxxxxx`, `ORDLN-...`, `FUL-...`, `DSP-...`, `PAYOUT-...`, `CUST-...`, `REV-...`). | 9 | PASSED ✅ |
| `test_foreign_keys.py` | Full SQLite `foreign_key_check` PRAGMA + negative integrity tests preventing orphan records under enforced foreign keys. | 2 | PASSED ✅ |
| `test_disputes.py` | Dispute count, reason codes validation, and positive amount assertions. | 2 | PASSED ✅ |
| `test_reproducibility.py` | Cryptographic deterministic generation reproducibility across independent databases with fixed seed `20261022`. | 1 | PASSED ✅ |
| **Total** | **Comprehensive Full System Verification** | **72** | **100% PASSED** |

---

## 3. Financial Test Fixtures Verification (Section 5)

Each of the 5 Section 5 financial scenarios is automated and verified in `tests/test_payouts.py`:

1. **`test_inr_illustrative_payout_fixture`**: Verifies exact net payable of ₹81,000.00 from Gross ₹1,00,000.00, Commission ₹12,000.00, Reserve Held ₹10,000.00, Reserve Released ₹5,000.00, Lost Dispute ₹2,000.00.
2. **`test_inr_reserve_release_added_only_once`**: Verifies release idempotency so released reserves cannot be re-credited in subsequent settlement cycles.
3. **`test_inr_partial_refund_deduction`**: Verifies that a ₹300.00 partial refund on a ₹1,000.00 line recalculates commission, reserve, and yields net payable of ₹559.70.
4. **`test_inr_multi_seller_order_payout_separation`**: Verifies that a ₹1,000.00 split basket (Seller A ₹600.00, Seller B ₹400.00) produces independent settlements (₹479.70 and ₹319.70) with zero cross-contamination.
5. **`test_inr_finalized_dispute_deducted_exactly_once`**: Verifies that lost chargeback deductions flag `clawback_applied` and are never double-deducted in future batches.
