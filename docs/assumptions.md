# Architecture & Business Assumptions
**SellerOps Intelligence Platform**

---

## 1. Marketplace Model Assumptions
1. **Multi-Sided Platform:** The platform models a managed multi-sided marketplace where independent third-party merchants list products and consumers purchase goods across split baskets.
2. **Deterministic Time Horizon:** Orders, shipments, reviews, disputes, and settlements are generated over a realistic simulated timeline spanning 2024 through November 2026 with a fixed seed (`20261022`).
3. **Currency Standardization (INR Mandate):** All monetary figures across the platform are strictly denominated in **Indian Rupees (INR – ₹)** with minor unit `paise` (1 Rupee = 100 paise).
   - Internal storage in SQLite uses integer paise (`_cents` columns) to ensure exact zero-drift monetary arithmetic.
   - Calculations use Python `Decimal` with `ROUND_HALF_UP`.
   - UI and exports render using the standard Indian numbering system (`en_IN` locale: Lakhs and Crores).
4. **Primary Logistics Channel:** Merchants fulfill orders through integrated logistics partners (FedEx, UPS, USPS, DHL) with automated tracking numbers and lifecycle state transitions.

---

## 2. Risk & Operational Assumptions
1. **48-Hour Dispatch Benchmark:** Industry-standard 48-hour dispatch SLA window is enforced. Dispatch delays exceeding 48 hours increase late shipment rates and impact merchant risk scores.
2. **Rolling Reserve Collateral:** Reserves are held by the platform in a designated escrow ledger until the return and dispute hold window elapses (7 to 30 days depending on seller tier).
3. **Suspended Merchant Quarantine:** When a merchant is flagged as `SUSPENDED`, all existing listings must be suppressed (`status = 'SUSPENDED'`) and payouts locked. Any active inventory or sales by a suspended merchant constitutes a critical compliance violation.
4. **Ground-Truth Rigor:** Injected operational anomalies are modeled after real-world marketplace billing and accounting failures (e.g. race conditions in batch disbursement, ERP double-counting, disconnected dispute webhooks). Ground truth is strictly separated from operational data.
