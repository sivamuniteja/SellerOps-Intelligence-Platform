# SellerOps Intelligence Platform
*Enterprise Multi-Sided Marketplace Operations, SLA Monitoring & Financial Reconciliation Engine*

[![Python](https://img.shields.io/badge/Python-3.13+-2563EB.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B.svg)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/SQLite-3.0+-003B57.svg)](https://www.sqlite.org/)
[![PyTest](https://img.shields.io/badge/PyTest-18%20Passed-16A34A.svg)](https://pytest.org/)
[![Anomaly Detection](https://img.shields.io/badge/F1--Score-1.0000-16A34A.svg)]()

Developed for the **YottaFlex AI Round 3 – 72 Hours Code Challenge**.

---

## 🚀 Quick Start: Run the Website in VS Code

### 1. Installation & Environment Setup
Clone or open the repository in VS Code, then install dependencies:
```bash
# Verify or install required packages
pip install -r requirements.txt
```

### 2. Launch the Web Application
Run the Streamlit enterprise dashboard:
```bash
streamlit run dashboard/app.py
```
The website will open automatically at `http://localhost:8501`.

---

## 🛠️ CLI Utilities & Commands

### Generate Synthetic Datasets
Generate either the rapid test dataset or the full 100k-order dataset:
```bash
# Starter Dataset (200 sellers, 2,000 listings, 10,000 orders, 1,000 disputes) ~0.5s
python3 scripts/generate_data.py --target starter

# Full Dataset (2,000 sellers, 20,000 listings, 100,000 orders, 10,000 disputes) ~6.0s
python3 scripts/generate_data.py --target full
```

### Validate Data & Detect Anomalies
Run the end-to-end audit CLI (referential integrity, lifecycle chronology, reconciliation, and anomaly detection):
```bash
python3 scripts/validate_data.py
```

### Verify Deterministic Reproducibility
Verify that independent generation runs produce identical cryptographic SHA-256 table hashes:
```bash
python3 scripts/reproduce_data.py
```

### Run Automated PyTest Suite
Execute the unit, integration, and anomaly benchmark test suite:
```bash
pytest tests/ -v
```

---

## 📁 Project Structure

```
SellerOps-Intelligence-Platform/
├── README.md                          # Project documentation and quickstart
├── requirements.txt                   # Pinned Python package dependencies
├── .gitignore                         # Git exclusion rules
├── config.yaml                        # Platform parameters, SLA thresholds, fee schedules
├── .streamlit/
│   └── config.toml                    # Enforces pure white theme and light mode
│
├── src/
│   ├── __init__.py                    # Core package init
│   ├── config.py                      # Typed configuration loader & validator
│   ├── generate.py                    # Master synthetic pipeline orchestrator
│   │
│   ├── generators/                    # Deterministic data generators (Seed 42)
│   │   ├── sellers.py                 # 2,000 sellers across 5 SLA tiers
│   │   ├── customers.py               # 10,000 realistic customer profiles
│   │   ├── listings.py                # 20,000 product listings + Anomaly 3
│   │   ├── orders.py                  # 100,000 order transactions
│   │   ├── fulfillments.py            # Carrier transit & SLA tracking
│   │   ├── reviews.py                 # Correlated customer ratings
│   │   ├── disputes.py                # 10,000 disputes & claims + Anomaly 4
│   │   └── payouts.py                 # Settlements, reserves & payouts + Anomalies 1, 2, 5
│   │
│   ├── models/
│   │   ├── schema.sql                 # DDL script with foreign keys & CHECK constraints
│   │   └── entities.py                # Pydantic domain models
│   │
│   ├── services/                      # Core business logic engines
│   │   ├── commission_engine.py       # Category rates, tier discounts, minimum fees
│   │   ├── reserve_engine.py          # Risk-based rolling reserve calculation
│   │   ├── payout_engine.py           # Eligibility criteria & batch disbursement
│   │   ├── seller_metrics.py          # Seller scorecards (LSR, ODR, CR, Risk Score)
│   │   └── fulfillment_engine.py      # 48-hour dispatch SLA evaluator
│   │
│   ├── validation/                    # Audit & anomaly detection
│   │   ├── integrity.py               # Foreign key and primary key verification
│   │   ├── reconciliation.py          # General ledger balance & payout matching
│   │   ├── lifecycle.py               # FSM temporal state machine validation
│   │   └── anomaly_detection.py       # Detection rules for 5 negative scenarios
│   │
│   ├── database/
│   │   └── connection.py              # SQLite connection manager with WAL mode
│   │
│   └── exports/                       # Multi-format data exporters
│       ├── csv_export.py              # Streaming CSV exporter
│       ├── json_export.py             # Structured JSON exporter
│       └── sql_export.py              # Full database SQL dump
│
├── dashboard/
│   ├── app.py                         # Main Streamlit landing console
│   ├── theme.py                       # Pure white enterprise CSS & Plotly layouts
│   └── pages/                         # 12 Specialized Operational Consoles
│       ├── 1_Overview.py              # Executive macro KPIs & volume trends
│       ├── 2_Sellers.py               # Seller directory, risk scores, tier progression
│       ├── 3_Listings.py              # 20,000 SKU catalog & price distributions
│       ├── 4_Orders.py                # 100,000 order pipeline & payment methods
│       ├── 5_Fulfillment.py           # Carrier SLA performance (FedEx, UPS, USPS, DHL)
│       ├── 6_Disputes.py              # 10,000 dispute analysis & loss rates
│       ├── 7_Commissions.py           # Platform take-rates & fee auditing
│       ├── 8_Payouts.py               # Payout batches, reserve holds, bank schedules
│       ├── 9_Reconciliation.py        # Ledger balance & variance detection
│       ├── 10_Anomalies.py            # Flagship Anomaly Detection Center
│       ├── 11_Data_Quality.py         # Schema constraint & foreign key matrix
│       └── 12_Reports.py              # Downloadable operational CSV/JSON/SQL exports
│
├── tests/                             # PyTest automated test suite
│   ├── test_ids.py                    # Canonical ID regex pattern tests
│   ├── test_foreign_keys.py           # Referential integrity & orphan prevention tests
│   ├── test_commissions.py            # Commission engine & fee floor tests
│   ├── test_payouts.py                # Reserve holds & eligibility tests
│   ├── test_disputes.py               # Dispute lifecycle & positive value assertions
│   ├── test_anomalies.py              # 100% precision/recall anomaly benchmarks
│   └── test_reproducibility.py        # Independent deterministic generation tests
│
├── docs/                              # Comprehensive documentation suite
│   ├── architecture.md                # System components & data pipeline architecture
│   ├── schema.md                      # Relational schema ER diagram & table constraints
│   ├── data_dictionary.md             # Column-by-column dictionary for all 11 tables
│   ├── business_rules.md              # Commission schedules, reserve rules, SLA limits
│   ├── validation_report.md           # Integrity audit & anomaly benchmark report
│   ├── testing_report.md              # Test execution log & coverage matrix
│   ├── assumptions.md                 # Marketplace operational assumptions
│   └── limitations.md                 # System boundaries & future roadmap
│
├── prompts/
│   └── ai_prompt_history.md           # AI prompt history & development audit log
│
├── manifests/
│   ├── source_manifest.json           # Environment snapshot & generator mapping
│   └── generation_summary.json        # Execution metrics & record counts
│
├── data/
│   ├── starter/                       # Fast 10k order starter database
│   ├── full/                          # Complete 100k order database
│   └── scenarios/                     # Export staging & reproducibility testing
│
└── scripts/
    ├── generate_data.py               # CLI generator script
    ├── validate_data.py               # CLI validation & anomaly audit script
    └── reproduce_data.py              # CLI deterministic hash verification script
```

---

## 🚨 Operational Negative Scenarios (Anomalies)

The platform deterministically injects and detects the 5 required operational exceptions:

| Anomaly Code | Scenario Description | Ground Truth Count | Detection Accuracy | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **Anomaly 1** | Payout Before Delivery or Hold Release | 25 records | **100.0% Precision / Recall** | `CRITICAL` |
| **Anomaly 2** | Commission Applied Twice | 25 records | **100.0% Precision / Recall** | `HIGH` |
| **Anomaly 3** | Suspended Seller Continues Listing | 20 records | **100.0% Precision / Recall** | `CRITICAL` |
| **Anomaly 4** | Dispute Not Deducted (Unclawbacked Chargeback) | 25 records | **100.0% Precision / Recall** | `HIGH` |
| **Anomaly 5** | Payout Total Does Not Equal Payout Lines | 20 records | **100.0% Precision / Recall** | `CRITICAL` |
| **TOTAL** | **Consolidated Anomaly Benchmark** | **115 records** | **F1-Score: 1.0000** | - |

---

## 🎨 Visual Design System Compliance

- **Canvas Background:** Pure White (`#FFFFFF`).
- **Primary Typography:** Charcoal Near-Black (`#111827`).
- **Secondary Typography:** Slate (`#64748B`).
- **Primary Brand Blue:** `#2563EB`.
- **Status Accents:** Success (`#16A34A`), Warning (`#D97706`), Critical Error (`#DC2626`).
- **Border Lines:** Slate (`#E2E8F0`).
- **Elevation:** White cards with subtle drop shadows (`box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05)`).
- **Charts:** Cohesive Plotly light layouts with restrained color palettes.
- **Dark Mode:** Explicitly disabled.

---

## 📜 License
Developed for the YottaFlex AI Round 3 Challenge. All rights reserved.
