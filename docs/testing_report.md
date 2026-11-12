# Automated Testing & Test Execution Report
**SellerOps Intelligence Platform**  
*Test Framework: PyTest 8.3.4 | Python 3.13.5*

---

## 1. Test Suite Summary

The automated test suite in `tests/` verifies data integrity, foreign key constraints, commission calculations, rolling reserve mechanics, dispute operations, anomaly detection benchmarks, and cryptographic reproducibility.

```
============================= test session starts ==============================
platform darwin -- Python 3.13.5, pytest-8.3.4, pluggy-1.5.0
rootdir: /Users/pallamalamunisivateja/SellerOps Intelligence Platform
collected 18 items

tests/test_anomalies.py::test_detect_all_anomalies PASSED                [  5%]
tests/test_commissions.py::test_standard_category_commission PASSED      [ 11%]
tests/test_commissions.py::test_enterprise_tier_commission_discount PASSED [ 16%]
tests/test_commissions.py::test_minimum_commission_floor PASSED          [ 22%]
tests/test_disputes.py::test_disputes_count_and_reasons PASSED           [ 27%]
tests/test_disputes.py::test_dispute_amounts_positive PASSED             [ 33%]
tests/test_foreign_keys.py::test_no_foreign_key_violations PASSED        [ 38%]
tests/test_foreign_keys.py::test_foreign_key_enforcement_prevents_orphan PASSED [ 44%]
tests/test_ids.py::test_id_format[sellers-col_and_pattern0] PASSED       [ 50%]
tests/test_ids.py::test_id_format[customers-col_and_pattern1] PASSED     [ 55%]
tests/test_ids.py::test_id_format[listings-col_and_pattern2] PASSED      [ 61%]
tests/test_ids.py::test_id_format[orders-col_and_pattern3] PASSED        [ 66%]
tests/test_ids.py::test_id_format[fulfillments-col_and_pattern4] PASSED  [ 72%]
tests/test_ids.py::test_id_format[reviews-col_and_pattern5] PASSED       [ 77%]
tests/test_ids.py::test_id_format[disputes-col_and_pattern6] PASSED      [ 83%]
tests/test_ids.py::test_id_format[payout_batches-col_and_pattern7] PASSED [ 88%]
tests/test_payouts.py::test_reserve_calculation_and_eligibility PASSED   [ 94%]
tests/test_reproducibility.py::test_generation_reproducibility PASSED    [100%]

============================== 18 passed in 2.24s ==============================
```

---

## 2. Test File Coverage Matrix

| Test Module | Coverage & Verification Scope | Test Result |
| :--- | :--- | :--- |
| `test_ids.py` | Regex pattern validation across all 8 canonical ID formats (`SLR-xxxxx`, `ORD-xxxxxx`, etc.). | PASSED ✅ |
| `test_foreign_keys.py` | Full SQLite `foreign_key_check` PRAGMA + negative test ensuring orphan records raise `IntegrityError`. | PASSED ✅ |
| `test_commissions.py` | Category base rates, tier volume discounts, minimum commission floor (\$0.50), and \$0.30 fixed fee. | PASSED ✅ |
| `test_payouts.py` | Risk-based reserve hold calculation, hold window duration, and 4-point eligibility criteria. | PASSED ✅ |
| `test_disputes.py` | Dispute count, reason codes validation, and positive amount assertions. | PASSED ✅ |
| `test_anomalies.py` | Precision, recall, and count assertions for all 5 operational exception scenarios. | PASSED ✅ |
| `test_reproducibility.py` | Deterministic generation across independent databases with seed 42 matching SHA-256 hashes. | PASSED ✅ |

---

## 3. How to Run the Automated Tests

From the project root in VS Code or Terminal:
```bash
# Run complete test suite
pytest tests/ -v

# Run individual test files
pytest tests/test_anomalies.py -v
pytest tests/test_commissions.py -v
pytest tests/test_foreign_keys.py -v
```
