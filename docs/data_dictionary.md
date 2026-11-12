# Comprehensive Data Dictionary v2.0
**SellerOps Intelligence Platform**

---

### 1. `schema_migrations`
Tracks versioned migration execution.
| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `version` | INTEGER | NO | PK | Sequential migration index. |
| `description` | TEXT | NO | - | Migration description summary. |
| `applied_at` | TEXT | NO | - | ISO-8601 execution timestamp. |

---

### 2. `sellers`
Primary merchant accounts.
| Column | Type | Nullable | Default | Constraints & Description |
| :--- | :--- | :--- | :--- | :--- |
| `seller_id` | VARCHAR(32) | NO | PK | Format: `SELL-000001`. |
| `name` | VARCHAR(128) | NO | - | Registered merchant trading name. |
| `tier` | VARCHAR(32) | NO | - | `STANDARD`, `PREFERRED`, `ENTERPRISE`, `PROBATION`, `SUSPENDED`. |
| `status` | VARCHAR(32) | NO | - | `ACTIVE`, `PROBATION`, `SUSPENDED`, `UNDER_REVIEW`. |
| `risk_score` | REAL | NO | - | Computed composite risk index ($0.0 \le \text{score} \le 100.0$). |
| `rating` | REAL | NO | - | Average review rating ($1.0 \le \text{rating} \le 5.0$). |
| `onboarding_date` | TEXT | NO | - | Merchant onboarding timestamp. |
| `bank_account_verified` | INTEGER | NO | 1 | KYC & bank verification status (`0` or `1`). |
| `country` | VARCHAR(32) | NO | 'USA' | Operating jurisdiction. |
| `created_at` | TEXT | NO | - | Record creation timestamp. |
| `updated_at` | TEXT | NO | - | Last modification timestamp. |

---

### 3. `seller_status_events`
Immutable audit log of merchant status changes.
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `event_id` | VARCHAR(32) | NO (PK) | Format: `SSE-000001`. |
| `seller_id` | VARCHAR(32) | NO (FK) | References `sellers(seller_id)`. |
| `previous_status` | VARCHAR(32) | YES | Prior status code. |
| `new_status` | VARCHAR(32) | NO | New status code. |
| `reason` | TEXT | NO | Operational justification (e.g. LSR breach). |
| `created_at` | TEXT | NO | Event log timestamp. |

---

### 4. `customers`
Consumer accounts.
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `customer_id` | VARCHAR(32) | NO (PK) | Format: `CUST-000001`. |
| `name` | VARCHAR(128) | NO | Full customer name. |
| `email` | VARCHAR(128) | NO | Contact email address (UNIQUE). |
| `city` | VARCHAR(64) | NO | Delivery city. |
| `state` | VARCHAR(32) | NO | Delivery state / territory. |
| `country` | VARCHAR(32) | NO | Delivery country code. |
| `created_at` | TEXT | NO | Account creation date. |

---

### 5. `listings`
Catalog products published by merchants.
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `listing_id` | VARCHAR(64) | NO (PK) | Format: `LIST-SELL-000001-000001`. |
| `seller_id` | VARCHAR(32) | NO (FK) | References `sellers(seller_id)`. |
| `title` | VARCHAR(256) | NO | Product title. |
| `category` | VARCHAR(64) | NO | Category (e.g. `Electronics`, `Home & Kitchen`). |
| `price_cents` | INTEGER | NO | Unit price in integer paise ($> 0$). |
| `inventory_count` | INTEGER | NO | Available inventory count ($\ge 0$). |
| `status` | VARCHAR(32) | NO | `ACTIVE`, `OUT_OF_STOCK`, `SUSPENDED`, `ARCHIVED`. |
| `created_at` | TEXT | NO | Listing publication date. |
| `updated_at` | TEXT | NO | Last update timestamp. |

---

### 6. `commission_rules`
Category and tier fee policy matrix.
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `rule_id` | VARCHAR(32) | NO (PK) | Format: `CR-000001`. |
| `category` | VARCHAR(64) | NO | Target product category. |
| `seller_tier` | VARCHAR(32) | NO | Target merchant tier. |
| `base_rate_basis_points` | INTEGER | NO | Percentage in basis points ($800 = 8.00\%$). |
| `min_commission_cents` | INTEGER | NO | Minimum commission floor in paise ($50 = ₹0.50$). |
| `fixed_fee_cents` | INTEGER | NO | Fixed per-order processing charge in paise ($30 = ₹0.30$). |
| `effective_from` | TEXT | NO | Rule start date. |
| `effective_to` | TEXT | NO | Rule expiration date. |
| `is_active` | INTEGER | NO | Active status flag (`0` or `1`). |
| `created_at` | TEXT | NO | Rule creation timestamp. |

---

### 7. `orders`
Order transaction headers (supports multi-seller baskets).
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `order_id` | VARCHAR(32) | NO (PK) | Format: `ORD-2026-000001`. |
| `customer_id` | VARCHAR(32) | NO (FK) | References `customers(customer_id)`. |
| `order_date` | TEXT | NO | Purchase placement timestamp. |
| `total_amount_cents` | INTEGER | NO | Aggregate order gross total in integer paise. |
| `currency` | VARCHAR(8) | NO | Currency code (`INR`). |
| `payment_method` | VARCHAR(32) | NO | Payment instrument (e.g. `CREDIT_CARD`). |
| `order_status` | VARCHAR(32) | NO | `PLACED`, `CONFIRMED`, `PARTIALLY_SHIPPED`, `SHIPPED`, `DELIVERED`, `CANCELLED`, `RETURNED`. |
| `created_at` | TEXT | NO | Creation timestamp. |
| `updated_at` | TEXT | NO | Last status update timestamp. |

---

### 8. `order_lines`
Individual order item lines (multi-seller resolution).
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `order_line_id` | VARCHAR(48) | NO (PK) | Format: `ORDLN-2026-000001-01`. |
| `order_id` | VARCHAR(32) | NO (FK) | References `orders(order_id)`. |
| `seller_id` | VARCHAR(32) | NO (FK) | References merchant `sellers(seller_id)`. |
| `listing_id` | VARCHAR(64) | NO (FK) | References `listings(listing_id)`. |
| `line_number` | INTEGER | NO | Line item index within the order. |
| `quantity` | INTEGER | NO | Quantity ordered ($> 0$). |
| `unit_price_cents` | INTEGER | NO | Unit price in integer cents ($> 0$). |
| `gross_amount_cents` | INTEGER | NO | Gross line value (`quantity * unit_price_cents`). |
| `line_status` | VARCHAR(32) | NO | Line status lifecycle. |
| `created_at` | TEXT | NO | Line creation date. |

---

### 9. `fulfillments`
Shipment records supporting partial fulfillment.
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `fulfillment_id` | VARCHAR(64) | NO (PK) | Format: `FUL-ORDLN-2026-000001-01`. |
| `order_line_id` | VARCHAR(48) | NO (FK) | References `order_lines(order_line_id)`. |
| `order_id` | VARCHAR(32) | NO (FK) | References `orders(order_id)`. |
| `seller_id` | VARCHAR(32) | NO (FK) | References `sellers(seller_id)`. |
| `carrier` | VARCHAR(64) | NO | Integrated carrier (`FedEx`, `UPS`, `USPS`, `DHL`). |
| `tracking_number` | VARCHAR(128) | NO | Tracking reference. |
| `quantity_fulfilled` | INTEGER | NO | Number of units in this shipment. |
| `dispatched_at` | TEXT | YES | Warehouse dispatch timestamp. |
| `expected_delivery_at` | TEXT | YES | Carrier estimated arrival. |
| `delivered_at` | TEXT | YES | Confirmed delivery timestamp. |
| `sla_status` | VARCHAR(32) | NO | `ON_TIME`, `LATE`, `CANCELLED`, `IN_TRANSIT`. |
| `transit_days` | INTEGER | YES | Door-to-door transit duration in days. |
| `created_at` | TEXT | NO | Record timestamp. |

---

### 10. `fulfillment_events`
Immutable logistics tracking events.
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `event_id` | VARCHAR(32) | NO (PK) | Format: `FLE-000001`. |
| `fulfillment_id` | VARCHAR(64) | NO (FK) | References `fulfillments(fulfillment_id)`. |
| `event_type` | VARCHAR(32) | NO | Milestone (`PICKED_UP`, `IN_TRANSIT`, `DELIVERED`, etc.). |
| `event_timestamp` | TEXT | NO | Event occurrence timestamp. |
| `location` | VARCHAR(128) | YES | Transit facility location. |
| `notes` | TEXT | YES | Carrier milestone details. |
| `created_at` | TEXT | NO | Record creation timestamp. |

---

### 11. `customer_reviews`
Ratings and comments linked to completed order lines.
| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `review_id` | VARCHAR(32) | NO (PK) | Format: `REV-2026-000001`. |
| `order_line_id` | VARCHAR(48) | NO (FK) | Unique reference to `order_lines(order_line_id)`. |
| `order_id` | VARCHAR(32) | NO (FK) | References `orders(order_id)`. |
| `seller_id` | VARCHAR(32) | NO (FK) | References `sellers(seller_id)`. |
| `customer_id` | VARCHAR(32) | NO (FK) | References `customers(customer_id)`. |
| `rating` | INTEGER | NO | Rating ($1 \le \text{rating} \le 5$). |
| `comment` | TEXT | YES | Customer feedback prose. |
| `created_at` | TEXT | NO | Submission date. |

---

### 12. `disputes` & `dispute_events`
Dispute claims and immutable adjudication history.
- `disputes`: `dispute_id` (`DSP-2026-000001`), `disputed_amount_cents` (integer cents), `status` (`OPEN`, `UNDER_REVIEW`, `RESOLVED_BUYER_FAVOR`, `RESOLVED_SELLER_FAVOR`, `CHARGEBACK_LOST`), `clawback_applied` (`0` or `1`).
- `dispute_events`: `event_id` (`DSE-000001`), `actor` (`BUYER`, `SELLER`, `ARBITRATOR`, `SYSTEM`), `previous_status`, `new_status`.

---

### 13. `commission_ledger`
Immutable double-entry commission accounting entries.
- `entry_id` (`CML-000001`), `order_line_id` (FK), `seller_id` (FK), `rule_id` (FK), `gross_amount_cents`, `rate_basis_points`, `variable_fee_cents`, `fixed_fee_cents`, `total_commission_cents`.

---

### 14. `reserve_ledger`
Rolling collateral hold ledger.
- `entry_id` (`RSV-000001`), `order_line_id` (FK), `seller_id` (FK), `reserve_rate_basis_points`, `reserve_amount_cents`, `hold_days`, `release_scheduled_date`, `status` (`HELD`, `RELEASED`, `FORFEITED`).

---

### 15. `refunds`
Refund accounting adjustments.
- `refund_id` (`REF-2026-000001`), `order_id` (FK), `order_line_id` (FK), `dispute_id` (FK), `refund_amount_cents`.

---

### 16. `payouts`, `payout_lines` & `payout_events`
Banking disbursement batches and line item reconciliation.
- `payouts`: `payout_id` (`PAYOUT-2026-000001`), `seller_id` (FK), `net_payout_amount_cents`, `payout_status`, `reconciliation_status`.
- `payout_lines`: `line_id` (`PLN-PAYOUT-2026-000001-01`), `payout_id` (FK), `order_line_id` (FK), `net_line_amount_cents`.
- `payout_events`: `event_id` (`POE-000001`), `payout_id` (FK), `gateway_reference`, `new_status`.

---

### 17. `ground_truth`
Canonical operational anomaly registry.
- `anomaly_id` (`ANO-1-0001`), `anomaly_type`, `entity_type`, `entity_id`, `severity`, `detected`.
