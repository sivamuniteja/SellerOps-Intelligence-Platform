# SellerOps Intelligence Platform
*Enterprise Multi-Sided Marketplace Operations, SLA Monitoring & Financial Reconciliation Engine*

[![Python](https://img.shields.io/badge/Python-3.13+-2563EB.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B.svg)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/SQLite-3.0+-003B57.svg)](https://www.sqlite.org/)
[![PyTest](https://img.shields.io/badge/PyTest-92%20Passed-16A34A.svg)](https://pytest.org/)
[![Currency](https://img.shields.io/badge/Currency-INR%20(₹)-2563EB.svg)]()
[![Anomaly Detection](https://img.shields.io/badge/F1--Score-1.0000-16A34A.svg)]()

Developed for the **YottaFlex AI Round 3 – 72 Hours Code Challenge**.

---

## 🇮🇳 Global INR Currency Mandate

The platform enforces **Indian Rupees (INR – ₹)** as its sole currency standard:
- **Currency Code:** `INR`
- **Currency Symbol:** `₹`
- **Locale:** `en_IN`
- **Subunit:** `paise` (1 Rupee = 100 paise; 1 minor unit = 1/100th of main currency unit).
- **Zero Floating-Point Drift:** All internal database financial columns store exact 64-bit integer paise (`_cents` / minor units). All monetary calculations use Python `Decimal` with `ROUND_HALF_UP`.
- **Indian Number Grouping:** Rendered in standard Indian grouping format (e.g. `₹1,03,86,130.23`, `₹12.50 L`, `₹1.04 Cr`).
- **Complete Elimination:** Zero `$` or `USD` across database records, financial calculations, dashboard, reports, CSV/JSON/SQL exports, and documentation.

---

## 🚀 Quick Start: Run the Platform

### 1. Installation & Environment Setup
Clone or open the repository, then install dependencies:
```bash
# Verify or install required packages
pip install -r requirements.txt
```

### 2. Launch the Streamlit Enterprise Dashboard
```bash
streamlit run dashboard/app.py
```
The application will open automatically at `http://localhost:8501`.

---

## 🛠️ CLI Utilities & Commands

### Master Multi-Format Data Exporter (Phase 8)
Export all 19 database entities, isolated ground truth, validation audits, SHA-256 checksums, and manifests across CSV, JSON, and SQL formats:
```bash
# Full dataset export with automatic round-trip re-import verification
python3 -m src.exports.manager --out-dir data/exports

# Filtered export by seller or date range
python3 -m src.exports.manager --out-dir data/exports --seller-id SELL-000001
python3 -m src.exports.manager --out-dir data/exports --start-date 2026-01-01 --end-date 2026-03-31
```

### Generate Synthetic Datasets
Generate either the rapid starter test dataset or the full 100k-order dataset with deterministic seed `20261022`:
```bash
# Starter Dataset (50 sellers, 500 listings, 2,000 orders, 200 disputes)
python3 scripts/generate_data.py --target starter

# Full Dataset (2,000 sellers, 20,000 listings, 100,000 orders, 10,000 disputes)
python3 scripts/generate_data.py --target full
```

### Validate Data & Detect Anomalies
Run the end-to-end audit CLI (referential integrity, lifecycle chronology, financial reconciliation, and anomaly detection):
```bash
python3 scripts/validate_data.py
```

### Run Comprehensive Automated PyTest Suite
Execute the entire test suite covering all 20 challenge areas and 5 mandatory financial fixtures:
```bash
pytest tests/ -v
```
*(All 92 tests pass in ~5.6 seconds)*

---

## 📁 Project Structure

```
SellerOps-Intelligence-Platform/
├── README.md                          # Platform documentation and quickstart
├── requirements.txt                   # Pinned Python dependencies
├── config.yaml                        # Platform parameters, INR currency config, fee schedules
├── .streamlit/
│   └── config.toml                    # Enforces pure white theme and light mode
│
├── src/
│   ├── __init__.py                    # Core package init
│   ├── config.py                      # Typed configuration loader & validator (INR support)
│   ├── currency.py                    # INR monetary math, paise conversions, Indian grouping
│   ├── generate.py                    # Master deterministic pipeline orchestrator (Seed 20261022)
│   │
│   ├── generators/                    # Deterministic data generators (Strict dependency order)
│   │   ├── sellers.py                 # 2,000 sellers across 5 SLA tiers
│   │   ├── customers.py               # 10,000 realistic customer profiles
│   │   ├── listings.py                # 20,000 product listings + Anomaly 3
│   │   ├── orders.py                  # 100,000 order transactions (INR currency)
│   │   ├── fulfillments.py            # Carrier transit & SLA tracking (FedEx, UPS, USPS, DHL)
│   │   ├── reviews.py                 # Correlated customer ratings
│   │   ├── disputes.py                # 10,000 disputes & claims + Anomaly 4
│   │   └── payouts.py                 # Settlements, reserves & payouts + Anomalies 1, 2, 5
│   │
│   ├── models/
│   │   ├── schema.sql                 # DDL v2 with enforced foreign keys & CHECK constraints
│   │   └── entities.py                # Pydantic v2 domain entities & properties
│   │
│   ├── services/                      # 5 Independent Business Engines
│   │   ├── commission_engine.py       # Category rates, tier discounts, minimum fee guarantees
│   │   ├── reserve_engine.py          # Risk-based rolling reserve calculation & hold release
│   │   ├── fulfillment_engine.py      # 48-hour dispatch SLA evaluator & carrier latency
│   │   ├── payout_engine.py           # Eligibility criteria & exact net payable calculation
│   │   └── seller_metrics.py          # Seller scorecards (LSR, ODR, CR, Risk Score)
│   │
│   ├── validation/                    # Audit & Anomaly Detection Framework
│   │   ├── integrity.py               # Foreign key and primary key verification
│   │   ├── lifecycle.py               # FSM temporal state machine validation
│   │   ├── reconciliation.py          # General ledger balance & payout matching
│   │   ├── anomaly_detection.py       # Rule-based detector for 5 negative scenarios
│   │   └── validator.py               # Unified 14-dimension platform audit orchestrator
│   │
│   ├── database/
│   │   └── connection.py              # SQLite connection manager with WAL mode & FK enforcement
│   │
│   └── exports/                       # Enterprise Multi-Format Data Exporter (Phase 8)
│       ├── csv_export.py              # Memory-efficient chunked CSV exporter
│       ├── json_export.py             # Streaming JSON exporter
│       ├── sql_export.py              # Master SQL seed exporter & re-import verifier
│       └── manager.py                 # Master orchestrator, checksum generator, manifest compiler
│
├── dashboard/
│   ├── app.py                         # Enterprise dashboard landing page & macro KPIs
│   ├── theme.py                       # Pure white enterprise CSS, Plotly white layouts, INR helpers
│   └── pages/                         # 12 Specialized Operational Consoles
│       ├── 1_Overview.py              # Executive macro KPIs & volume trends
│       ├── 2_Sellers.py               # 2,000 seller directory, risk scores, tier drill-downs
│       ├── 3_Listings.py              # 20,000 SKU catalog & price distributions
│       ├── 4_Orders.py                # 100,000 order pipeline & multi-seller basket breakdown
│       ├── 5_Fulfillment.py           # Carrier SLA performance & dispatch delay analysis
│       ├── 6_Disputes.py              # 10,000 dispute analysis, chargebacks & loss rates
│       ├── 7_Commissions.py           # Category schedules, tier take-rates & fee auditing
│       ├── 8_Payouts.py               # Payout batches, rolling reserves & disbursement cycles
│       ├── 9_Reconciliation.py        # General ledger reconciliation & variance analysis
│       ├── 10_Anomalies.py            # Flagship Anomaly Detection Center (100% precision/recall)
│       ├── 11_Data_Quality.py         # 14-dimension data quality audit matrix
│       └── 12_Reports.py              # Dynamic operational report generator & export downloads
│
├── tests/                             # Comprehensive Automated PyTest Suite (92 Tests)
│   ├── test_ids.py                    # Canonical ID regex pattern verification
│   ├── test_foreign_keys.py           # Referential integrity & orphan prevention tests
│   ├── test_currency.py               # INR arithmetic, paise conversion & grouping tests
│   ├── test_commissions.py            # Category rules, effective dates, double charge prevention
│   ├── test_payouts.py                # Payout formulas, reserve releases, 5 INR fixtures
│   ├── test_fulfillment.py            # Lifecycle FSM transitions, SLA delays, event history
│   ├── test_disputes.py               # Dispute lifecycle, positive claim values, loss rates
│   ├── test_seller_metrics.py         # Seller scorecards, defect rates, breach detection
│   ├── test_anomalies.py              # 100% precision/recall anomaly detection benchmarks
│   ├── test_validation.py             # Unified 14-dimension data quality validator tests
│   ├── test_exports.py                # CSV, JSON, SQL export integrity & re-import tests
│   └── test_reproducibility.py        # Fixed-seed deterministic generation verification
│
├── docs/                              # Comprehensive Technical Documentation Suite
│   ├── architecture.md                # Component architecture, data flow & concurrency model
│   ├── schema.md                      # Relational schema ER diagram, keys, cardinalities & indices
│   ├── data_dictionary.md             # Column-by-column dictionary for all 19 entities
│   ├── business_rules.md              # Mathematical formulas, reserve policies, SLA rules
│   ├── validation_report.md           # 14-dimension validation results & benchmark report
│   ├── testing_report.md              # PyTest test execution matrix across all 92 tests
│   ├── assumptions.md                 # Operational assumptions & parameters
│   └── limitations.md                 # Architectural boundaries & scaling roadmap
│
├── prompts/
│   └── ai_prompt_history.md           # AI prompt history, engineering decisions & audit log
│
├── manifests/
│   ├── source_manifest.json           # Environment snapshot, INR metadata & table checksums
│   └── generation_summary.json        # Execution metrics & record counts
│
└── data/
    ├── sellerops.db                   # Master SQLite database (100k orders, 2k sellers, INR)
    └── exports/                       # Complete Phase 8 exports (CSV, JSON, SQL, checksums)
```

---

## 🚨 Operational Negative Scenarios (Anomaly Detection)

The platform deterministically injects and detects the 5 required operational exceptions with **100.0% Precision and 100.0% Recall (F1 = 1.0000)**:

| Anomaly Code | Scenario Description | Injected Count | Detected Count | Precision | Recall | Severity |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Anomaly 1** | Payout Before Delivery or Hold Release | 25 | 25 | 100.0% | 100.0% | `CRITICAL` |
| **Anomaly 2** | Commission Applied Twice | 25 | 25 | 100.0% | 100.0% | `HIGH` |
| **Anomaly 3** | Suspended Seller Continues Listing | 20 | 20 | 100.0% | 100.0% | `CRITICAL` |
| **Anomaly 4** | Dispute Not Deducted (Unclawbacked Chargeback) | 25 | 25 | 100.0% | 100.0% | `HIGH` |
| **Anomaly 5** | Payout Total Does Not Equal Payout Lines | 20 | 20 | 100.0% | 100.0% | `CRITICAL` |
| **TOTAL** | **Consolidated Anomaly Benchmark** | **115** | **115** | **100.0%** | **100.0%** | **F1: 1.0000** |

*Ground-truth labels are strictly isolated in `data/exports/ground_truth/` and the `ground_truth` table; validation and detection engines operate purely on operational data.*

---

## 🎨 Enterprise White Visual Design System

- **Canvas Background:** Pure White (`#FFFFFF`).
- **Sidebar Background:** Pure White (`#FFFFFF`) with subtle 1px border (`#E2E8F0`).
- **Primary Typography:** Charcoal Near-Black (`#111827`).
- **Secondary Typography:** Slate (`#64748B`).
- **Primary Accent Blue:** `#2563EB`.
- **Status Accents:** Success (`#16A34A`), Warning (`#D97706`), Critical Error (`#DC2626`).
- **Card Containers:** Pure White (`#FFFFFF`) with border (`#E2E8F0`) and subtle elevation (`box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04)`).
- **Charts:** Bespoke Plotly light layout with crisp white paper and light grid lines.
- **Dark Mode:** Explicitly disabled across all 12 modules.

---

## 📜 License
Developed for the YottaFlex AI Round 3 Challenge. All rights reserved.
