# System Limitations & Future Enhancements
**SellerOps Intelligence Platform**

---

## 1. Current System Limitations

1. **Embedded Single-Node Database:**
   - The platform utilizes SQLite 3 with Write-Ahead Logging (WAL). While SQLite provides extreme zero-setup portability and easily handles 100,000+ orders in under 7 seconds, it does not support distributed horizontal scaling or high-concurrency multi-master write operations.
2. **Simplified Multi-Currency:**
   - The platform currently models all transactions in `USD`. Foreign exchange (FX) conversion rates, cross-border remittance fees, and multi-currency payout wallets are not currently simulated.
3. **Static Tax Computation:**
   - Sales tax (state/local marketplace facilitator tax) and VAT are assumed to be handled outside the core seller settlement ledger.
4. **Synchronous Payout Batch Runs:**
   - Payout batches are simulated periodically rather than streaming live banking webhooks via ISO 20022 / NACHA ACH networks.

---

## 2. Recommended Future Roadmap

- **PostgreSQL / Distributed SQL Migration:** Add connection adapters for distributed relational databases (e.g. CockroachDB or AWS Aurora) for multi-region active-active deployments.
- **Real-Time Kafka Streaming:** Integrate Apache Kafka / Redpanda event streams to feed order and shipment events directly into an asynchronous anomaly detection worker.
- **Machine Learning Fraud Scoring:** Enhance rule-based risk scoring with an XGBoost / Isolation Forest model trained on merchant velocity and chargeback spikes.
