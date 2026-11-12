# System Limitations & Future Enhancements
**SellerOps Intelligence Platform**

---

## 1. Current System Limitations

1. **Embedded Single-Node Database:**
   - The platform utilizes SQLite 3 with Write-Ahead Logging (WAL) and PRAGMA foreign_keys = ON. While SQLite provides zero-setup portability and easily processes 100,000+ orders, 20,000 listings, and 1,000,000+ relational rows in under 6 seconds, it is single-node and does not support distributed horizontal scaling or high-concurrency multi-master write operations.
2. **Single Currency Focus (INR Standardization):**
   - The platform strictly enforces Indian Rupees (INR – ₹) across all ledgers, calculations, and reporting. Dynamic multi-currency cross-border foreign exchange (FX) conversion rates, cross-border remittance fees, and multi-currency payout wallets are deliberately not simulated.
3. **Marketplace Facilitator Tax / GST:**
   - Goods and Services Tax (GST) and Tax Collected at Source (TCS) are modeled outside the core seller settlement ledger; net payouts focus on gross sales, platform commissions, reserve collateral, refunds, and chargebacks.
4. **Batch-Oriented Disbursement Cycles:**
   - Payout batches are evaluated deterministically in settlement cycles rather than streaming real-time live banking webhooks via NEFT/RTGS/IMPS networks.

---

## 2. Recommended Future Roadmap

- **PostgreSQL / Distributed SQL Migration:** Add connection adapters for distributed relational databases (e.g. CockroachDB or AWS Aurora) for enterprise multi-region active-active deployments.
- **Real-Time Kafka Streaming:** Integrate Apache Kafka / Redpanda event streams to feed order, tracking, and dispute events directly into an asynchronous anomaly detection worker.
- **Machine Learning Fraud & Risk Scoring:** Enhance rule-based risk scoring with an XGBoost / Isolation Forest model trained on merchant velocity and chargeback spikes.
- **Automated Banking Gateway Adapters:** Implement direct API integrations for automated payout file generation (NPCI / Open Banking / RazorpayX / Stripe Connect).
