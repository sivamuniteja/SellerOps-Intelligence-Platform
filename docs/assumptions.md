# Architecture & Business Assumptions
**SellerOps Intelligence Platform**

---

## 1. Marketplace Model Assumptions
1. **Multi-Sided Platform:** The platform models a managed two-sided marketplace (similar to Amazon Seller Central or eBay Marketplace) where independent third-party merchants list products and consumers purchase goods.
2. **Deterministic Time Horizon:** Orders, shipments, and settlements are generated over a realistic simulated timeline spanning 2024 through November 2026.
3. **Currency Standardization:** All monetary figures are denominated in United States Dollars (`USD`) with two-decimal precision.
4. **Primary Fulfillment Channel:** Merchants fulfill orders through integrated major logistics partners (FedEx, UPS, USPS, DHL) with automated tracking numbers and webhooks reporting dispatch and delivery events.

---

## 2. Risk & Operational Assumptions
1. **48-Hour Dispatch Benchmark:** Industry-standard 48-hour dispatch SLA window is enforced. Dispatch delays exceeding 48 hours increase late shipment rates and impact merchant risk scores.
2. **Rolling Reserve Collateral:** Reserves are assumed to be held by the platform in a designated escrow account until the return and dispute window elapses (7 to 30 days depending on seller tier).
3. **Suspended Merchant Quarantine:** When a merchant is flagged as `SUSPENDED`, all existing listings must be suppressed (`status = 'SUSPENDED'`) and payouts locked. Any active inventory or sales by a suspended merchant constitutes a critical compliance violation.
4. **Ground-Truth Rigor:** Injected operational anomalies are modeled after real-world marketplace billing and accounting failures (e.g. race conditions in batch disbursement, ERP double-counting, disconnected dispute webhooks).
