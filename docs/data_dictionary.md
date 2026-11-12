# Data Dictionary
**SellerOps Intelligence Platform**

---

### Table: `sellers`
| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `seller_id` | VARCHAR(32) | NO | PK | Canonical seller identifier (`SLR-xxxxx`). |
| `name` | VARCHAR(128) | NO | - | Business trading name. |
| `tier` | VARCHAR(32) | NO | - | Tier: `STANDARD`, `PREFERRED`, `ENTERPRISE`, `PROBATION`, `SUSPENDED`. |
| `status` | VARCHAR(32) | NO | - | Account state: `ACTIVE`, `PROBATION`, `SUSPENDED`, `UNDER_REVIEW`. |
| `risk_score` | REAL | NO | - | Computed risk index from 0.0 (safest) to 100.0 (high risk). |
| `rating` | REAL | NO | - | Average customer feedback score (1.0 to 5.0). |
| `onboarding_date` | TEXT | NO | - | Date seller joined marketplace platform (`YYYY-MM-DD HH:MM:SS`). |
| `bank_account_verified` | INTEGER | NO | 1 | Flag indicating KYC & payout banking verification (0 or 1). |
| `country` | VARCHAR(32) | NO | 'USA' | Operating jurisdiction. |
| `created_at` | TEXT | NO | - | Record timestamp. |

---

### Table: `customers`
| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `customer_id` | VARCHAR(32) | NO | PK | Canonical customer identifier (`CST-xxxxx`). |
| `name` | VARCHAR(128) | NO | - | Full legal customer name. |
| `email` | VARCHAR(128) | NO | - | Contact email address. |
| `city` | VARCHAR(64) | NO | - | Billing/shipping city. |
| `state` | VARCHAR(32) | NO | - | Billing/shipping state code. |
| `country` | VARCHAR(32) | NO | 'USA' | Country of origin. |
| `created_at` | TEXT | NO | - | Customer registration timestamp. |

---

### Table: `listings`
| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `listing_id` | VARCHAR(32) | NO | PK | Canonical SKU identifier (`LST-xxxxxx`). |
| `seller_id` | VARCHAR(32) | NO | FK | Foreign key referencing `sellers.seller_id`. |
| `title` | VARCHAR(256) | NO | - | Product commercial title. |
| `category` | VARCHAR(64) | NO | - | Product category mapped to commission schedules. |
| `price` | REAL | NO | - | Unit sale price in USD (must be > 0.0). |
| `inventory_count` | INTEGER | NO | 0 | Available physical stock. |
| `status` | VARCHAR(32) | NO | - | Status: `ACTIVE`, `OUT_OF_STOCK`, `SUSPENDED`, `ARCHIVED`. |
| `created_at` | TEXT | NO | - | Catalog publication date. |

---

### Table: `orders`
| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `order_id` | VARCHAR(32) | NO | PK | Canonical order identifier (`ORD-xxxxxx`). |
| `customer_id` | VARCHAR(32) | NO | FK | Referencing `customers.customer_id`. |
| `seller_id` | VARCHAR(32) | NO | FK | Referencing `sellers.seller_id`. |
| `listing_id` | VARCHAR(32) | NO | FK | Referencing `listings.listing_id`. |
| `order_date` | TEXT | NO | - | Order placement timestamp. |
| `quantity` | INTEGER | NO | 1 | Units purchased (> 0). |
| `unit_price` | REAL | NO | - | Item unit price at purchase. |
| `gross_amount` | REAL | NO | - | Gross transaction value (`quantity * unit_price`). |
| `currency` | VARCHAR(8) | NO | 'USD' | Transaction currency. |
| `payment_method` | VARCHAR(32) | NO | - | Payment instrument (e.g. `CREDIT_CARD`, `PAYPAL`). |
| `order_status` | VARCHAR(32) | NO | - | Order state: `PLACED`, `CONFIRMED`, `SHIPPED`, `DELIVERED`, `CANCELLED`, `RETURNED`. |

---

### Table: `fulfillments`
| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `fulfillment_id` | VARCHAR(32) | NO | PK | Canonical fulfillment identifier (`FLF-xxxxxx`). |
| `order_id` | VARCHAR(32) | NO | FK | Unique reference to `orders.order_id`. |
| `carrier` | VARCHAR(64) | NO | - | Integrated logistics carrier (`FedEx`, `UPS`, `USPS`, `DHL`). |
| `tracking_number` | VARCHAR(128) | NO | - | Public tracking reference. |
| `dispatched_at` | TEXT | YES | - | Physical dispatch timestamp from warehouse. |
| `expected_delivery_at` | TEXT | YES | - | Estimated arrival target. |
| `delivered_at` | TEXT | YES | - | Confirmed delivery timestamp. |
| `sla_status` | VARCHAR(32) | NO | - | SLA rating: `ON_TIME`, `LATE`, `CANCELLED`, `IN_TRANSIT`. |
| `transit_days` | INTEGER | YES | - | Total door-to-door transit days. |

---

### Table: `disputes`
| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `dispute_id` | VARCHAR(32) | NO | PK | Canonical dispute claim identifier (`DSP-xxxxxx`). |
| `order_id` | VARCHAR(32) | NO | FK | Target `orders.order_id`. |
| `seller_id` | VARCHAR(32) | NO | FK | Target `sellers.seller_id`. |
| `customer_id` | VARCHAR(32) | NO | FK | Filing `customers.customer_id`. |
| `dispute_date` | TEXT | NO | - | Filing timestamp. |
| `dispute_reason` | VARCHAR(64) | NO | - | Root cause code (e.g. `ITEM_NOT_RECEIVED`). |
| `disputed_amount` | REAL | NO | - | Claim dollar amount in USD. |
| `status` | VARCHAR(32) | NO | - | State: `OPEN`, `UNDER_REVIEW`, `RESOLVED_BUYER_FAVOR`, `RESOLVED_SELLER_FAVOR`, `CHARGEBACK_LOST`. |
| `resolution_date` | TEXT | YES | - | Adjudication closure timestamp. |
| `clawback_applied` | INTEGER | NO | 0 | 1 if financial clawback deducted from seller, 0 otherwise. |

---

### Table: `order_settlements`
| Column | Type | Nullable | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `settlement_id` | VARCHAR(32) | NO | PK | Internal accounting settlement token (`STL-xxxxxx`). |
| `order_id` | VARCHAR(32) | NO | FK | Unique `orders.order_id`. |
| `seller_id` | VARCHAR(32) | NO | FK | Settled `sellers.seller_id`. |
| `gross_amount` | REAL | NO | - | Order GMV. |
| `commission_rate` | REAL | NO | - | Applied commission percentage. |
| `commission_amount` | REAL | NO | - | Total platform fee deducted (`variable + $0.30 fixed`). |
| `reserve_rate` | REAL | NO | - | Rolling reserve hold percentage. |
| `reserve_amount` | REAL | NO | - | Collateral withheld (`gross * reserve_rate`). |
| `reserve_release_date` | TEXT | NO | - | Maturity timestamp when reserve becomes eligible. |
| `reserve_released` | INTEGER | NO | 0 | 1 if release conditions met, 0 if held. |
| `net_seller_amount` | REAL | NO | - | Net payable amount to seller balance. |
| `is_eligible_for_payout` | INTEGER | NO | 0 | 1 if eligible for inclusion in payout batch. |

---

### Table: `payout_batches` & `payout_lines`
- `payout_batches`: Grouping of eligible orders disbursed to seller bank accounts (`payout_id`, `net_payout_amount`, `payout_status`, `reconciliation_status`).
- `payout_lines`: Itemized line entries linking individual orders to a disbursement batch (`line_id`, `payout_id`, `order_id`, `net_line_amount`).

---

### Table: `anomalies_ground_truth`
- Stores canonical record of all 115 injected negative test scenarios:
  - `anomaly_id`: Unique tag (`ANO-1-xxxx` through `ANO-5-xxxx`).
  - `anomaly_type`: Category code (`PREMATURE_PAYOUT`, `DOUBLE_COMMISSION`, `SUSPENDED_SELLER_ACTIVE`, `UNCLAWBACKED_DISPUTE`, `PAYOUT_TOTAL_MISMATCH`).
  - `entity_id`: Foreign reference to affected row ID.
  - `severity`: `HIGH` or `CRITICAL`.
