# SellerOps Intelligence Platform — Initial Implementation Audit Report
*Pre-Implementation System Audit & Root-Cause Analysis*  
*Challenge: YottaFlex AI Round 3 – 72 Hours Code Challenge*  
*Date of Audit: November 13, 2026*  
*Auditor: Senior Software Architect & Financial Systems Lead*

---

## 1. System Inventory & Architecture Mapping

- **Application Entry Point:** `dashboard/app.py` executed via `streamlit run dashboard/app.py --server.port 8501`.
- **Database Location:** `data/sellerops.db` (SQLite 3 with WAL mode, foreign keys enforced via `PRAGMA foreign_keys = ON`).
- **Database Schema:** 19 tables in `src/models/schema.sql` (Sellers, Customers, Listings, Commission Rules, Orders, Order Lines, Fulfillments, Events, Reviews, Disputes, Ledger, Payouts).
- **Synthetic Generator:** `src/generate.py` orchestrating deterministic generators in `src/generators/` with fixed seed `20261022`.
- **Currency Engine:** Centralized in `src/currency.py` with integer paise (1 Rupee = 100 paise) and Indian number grouping (`en_IN`).
- **Anomaly Detection:** Rule-based detection in `src/validation/anomaly_detection.py` evaluating against isolated ground-truth labels.
- **Reporting & Exports:** Streaming CSV, JSON, and SQL seed script in `src/exports/` with SHA-256 checksums and re-import verification.

---

## 2. Comprehensive Issue Registry & Action Plan

| Issue ID | File & Function | Description | Root Cause | Business Impact | Required Correction | Verification Test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ISSUE-01** | `dashboard/theme.py`<br>`CUSTOM_CSS (.metric-card)` | KPI values overflow card boundaries or get clipped on desktop/tablet widths. | Fixed `font-size: 1.85rem` without responsive scaling, lack of flexbox `min-height`, and no `word-break`. | Critical financial numbers (e.g. GMV ₹1.04 Cr) appear truncated, destroying executive trust. | Implement responsive CSS with `clamp()`, `overflow-wrap: anywhere`, flexbox auto-height, and full value tooltips. | `tests/test_ui_formatting.py` + Browser inspection at 1440px, 1280px, 1024px, 768px, 390px. |
| **ISSUE-02** | `dashboard/theme.py`<br>`render_metric_card` | Unequal card heights within the same KPI row across all 12 dashboard pages. | Varying subtitle lengths (1 vs 2 lines or none) cause cards in adjacent `st.columns()` to have different heights. | Visual misalignment; breaks enterprise SaaS aesthetics. | Add flex container with `min-height: 120px` and `justify-content: space-between`. | Visual audit across Overview, Sellers, Listings, Orders, and Payouts. |
| **ISSUE-03** | `dashboard/pages/2_Sellers.py`<br>Line 229 (`render_metric_card`) | Suspended merchant details show "Account Active" label. | Hardcoded string `"Account Active"` passed as subtitle regardless of actual merchant `status`. | False compliance state; operational contradiction that alarms auditors. | Dynamically derive subtitle: `"Account Suspended"` for SUSPENDED, `"Probationary Standing"` for PROBATION, `"Account Active"` for ACTIVE. | Unit test verifying status-to-label mapping for suspended seller drill-down. |
| **ISSUE-04** | `dashboard/pages/11_Data_Quality.py`<br>Lines 54-65 | Successful database structural integrity audit masquerades as full business-rule PASS. | Top 5 KPI cards only reflected schema PRAGMA and PK/FK checks, omitting financial & compliance discrepancy counters. | Misleads executive team into believing zero business anomalies exist when 115 injected anomalies are present. | Restructure into 5 distinct audit pillars: Structural DB Integrity, Schema Validity, Lifecycle Chronology, Financial Reconciliation, and Operational Anomalies. | `tests/test_validation.py` asserting independent pillar statuses. |
| **ISSUE-05** | `dashboard/theme.py`<br>`CUSTOM_CSS` (Multi-Select) | Multi-select filter chips are truncated and clipped in multi-column layouts. | BaseWeb tag elements inside `.stMultiSelect` lack line wrapping and flex expansion. | Users cannot read selected categories or tiers when multiple filters are selected. | Inject scoped CSS overriding BaseWeb tag display to wrap tags with ellipsis and expand input container. | Visual check on Listings, Orders, and Commissions filter panels. |
| **ISSUE-06** | `dashboard/pages/*.py`<br>DataFrames | Data table columns for canonical IDs (`LIST-SELL-...`, `FUL-ORDLN-...`) are clipped. | Default `st.dataframe` assigns equal narrow widths to string columns. | Key relational identifiers cannot be read without horizontal scrolling. | Apply `st.column_config.TextColumn` with explicit minimum widths and text wrapping. | Data table readability inspection on Orders, Fulfillments, and Listings pages. |
| **ISSUE-07** | `src/services/payout_engine.py`<br>`calculate_net_payable_cents` | Need verification of exact Phase 5 illustrative test fixture. | The payout engine must support the exact formula: Gross ₹10,000 - Commission ₹1,000 - Refund ₹500 - Dispute ₹200 - Reserve ₹415 = Net ₹7,885.00. | Financial precision benchmark verification. | Implement and verify `test_phase5_mandatory_illustrative_fixture` in `tests/test_payouts.py`. | Automated pytest verifying exact ₹7,885.00 (788,500 paise). |
| **ISSUE-08** | `dashboard/pages/10_Anomalies.py`<br>Lines 38-48 | Dynamic evaluation of anomaly metrics against ground truth. | Ensure Precision, Recall, and F1 score are derived dynamically from `evaluate_against_ground_truth` and not statically asserted. | Audit validity; prevents accusation of fabricated metrics. | Confirm dynamic evaluation against `ground_truth` table with real TP, FP, FN counts. | `tests/test_anomalies.py` verifying precision/recall/F1 calculation. |
| **ISSUE-09** | `src/currency.py`<br>`format_inr` | Large monetary amounts in compact format need high precision without loss. | Compact formatting in Lakhs and Crores must correctly handle boundary values (e.g. ₹99,999 vs ₹1,00,000). | Minor formatting bugs at thresholds. | Add comprehensive boundary test suite for Indian number formatting (`1 Lakh`, `1 Crore`, `10 Crore`). | `tests/test_currency.py` covering all boundary conditions. |
| **ISSUE-10** | `src/services/seller_metrics.py`<br>`get_seller_scorecard` | Centralized definition of platform KPIs across dashboard pages. | Independent SQL queries across pages could drift if WHERE clauses differ. | Inconsistent GMV or active seller counts across Overview vs Sellers vs Reports. | Centralize platform metric queries in `src/services/seller_metrics.py` or shared database helper. | Reconciliation assertions comparing Overview metrics with individual console queries. |

---

## 3. Implementation Phasing & Roadmap

1. **Phase 2:** Global UI Alignment, Responsive CSS Design System, Non-Clipping KPI Cards, Responsive Tables, Multi-Select Styling.
2. **Phase 3 & 4:** Synthetic Data Generation Integrity, Canonical ID Regex Compliance, Strict Dependency DAG.
3. **Phase 5:** Financial Engine INR Precision, Mandatory Phase 5 Test Fixture (`₹7,885.00`), Reserve Base Options.
4. **Phase 6 & 7:** Complete 12 Dashboard Pages Repair, Dynamic Seller Status Labels, Separate Audit Pillars in Data Quality, Dynamic Anomaly Metrics.
5. **Phase 8 & 9:** SQLite WAL Performance, Index Optimization on Filtered Columns, Parameterized SQL.
6. **Phase 10:** Complete Automated PyTest Suite including `test_ui_formatting.py`, `test_order_reconciliation.py`, `test_reserve_engine.py`, `test_lifecycle.py`, `test_dashboard_metrics.py`.
7. **Phase 11:** Headless Browser Responsive Inspection across 1440px, 1280px, 1024px, 768px, 390px, 360px.
8. **Phase 12 & 13:** Documentation Updates and Final Acceptance Audit Report (`docs/final_acceptance_report.md`).
