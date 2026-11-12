# Relational Schema Specification
**SellerOps Intelligence Platform**

---

## 1. Entity Relationship Overview

```mermaid
erDiagram
    SELLERS ||--o{ LISTINGS : owns
    SELLERS ||--o{ ORDERS : fulfills
    SELLERS ||--o{ ORDER_SETTLEMENTS : receives
    SELLERS ||--o{ PAYOUT_BATCHES : paid_via
    CUSTOMERS ||--o{ ORDERS : places
    LISTINGS ||--o{ ORDERS : purchased_in
    ORDERS ||--|| FULFILLMENTS : tracked_by
    ORDERS ||--o| REVIEWS : receives
    ORDERS ||--o{ DISPUTES : subject_of
    ORDERS ||--|| ORDER_SETTLEMENTS : settled_by
    PAYOUT_BATCHES ||--o{ PAYOUT_LINES : contains
    ORDERS ||--o{ PAYOUT_LINES : disbursed_in

    SELLERS {
        string seller_id PK
        string name
        string tier
        string status
        float risk_score
        float rating
        string onboarding_date
    }
    CUSTOMERS {
        string customer_id PK
        string name
        string email
        string city
        string state
    }
    LISTINGS {
        string listing_id PK
        string seller_id FK
        string title
        string category
        float price
        int inventory_count
        string status
    }
    ORDERS {
        string order_id PK
        string customer_id FK
        string seller_id FK
        string listing_id FK
        string order_date
        int quantity
        float unit_price
        float gross_amount
        string order_status
    }
    FULFILLMENTS {
        string fulfillment_id PK
        string order_id FK
        string carrier
        string tracking_number
        string dispatched_at
        string delivered_at
        string sla_status
    }
    DISPUTES {
        string dispute_id PK
        string order_id FK
        string seller_id FK
        string customer_id FK
        string dispute_date
        string dispute_reason
        float disputed_amount
        string status
        int clawback_applied
    }
    ORDER_SETTLEMENTS {
        string settlement_id PK
        string order_id FK
        string seller_id FK
        float gross_amount
        float commission_rate
        float commission_amount
        float reserve_rate
        float reserve_amount
        string reserve_release_date
        int reserve_released
        float net_seller_amount
        int is_eligible_for_payout
    }
    PAYOUT_BATCHES {
        string payout_id PK
        string seller_id FK
        string batch_date
        int total_orders_count
        float gross_sales
        float total_commission
        float total_reserve_held
        float net_payout_amount
        string payout_status
        string reconciliation_status
    }
    PAYOUT_LINES {
        string line_id PK
        string payout_id FK
        string order_id FK
        float order_amount
        float commission_deducted
        float reserve_deducted
        float net_line_amount
    }
```

---

## 2. Table Definitions & Constraints

### 2.1 `sellers`
- **Primary Key:** `seller_id` (`SLR-xxxxx`)
- **Constraints:**
  - `tier IN ('STANDARD', 'PREFERRED', 'ENTERPRISE', 'PROBATION', 'SUSPENDED')`
  - `status IN ('ACTIVE', 'PROBATION', 'SUSPENDED', 'UNDER_REVIEW')`
  - `risk_score BETWEEN 0.0 AND 100.0`
  - `rating BETWEEN 1.0 AND 5.0`

### 2.2 `customers`
- **Primary Key:** `customer_id` (`CST-xxxxx`)
- **Attributes:** `name`, `email`, `city`, `state`, `country`, `created_at`

### 2.3 `listings`
- **Primary Key:** `listing_id` (`LST-xxxxxx`)
- **Foreign Key:** `seller_id REFERENCES sellers(seller_id)`
- **Constraints:** `price > 0.0`, `inventory_count >= 0`, `status IN ('ACTIVE', 'OUT_OF_STOCK', 'SUSPENDED', 'ARCHIVED')`

### 2.4 `orders`
- **Primary Key:** `order_id` (`ORD-xxxxxx`)
- **Foreign Keys:**
  - `customer_id REFERENCES customers(customer_id)`
  - `seller_id REFERENCES sellers(seller_id)`
  - `listing_id REFERENCES listings(listing_id)`
- **Constraints:** `quantity > 0`, `gross_amount > 0.0`, `order_status IN ('PLACED', 'CONFIRMED', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED')`

### 2.5 `fulfillments`
- **Primary Key:** `fulfillment_id` (`FLF-xxxxxx`)
- **Foreign Key:** `order_id UNIQUE REFERENCES orders(order_id)`
- **Constraints:** `sla_status IN ('ON_TIME', 'LATE', 'CANCELLED', 'IN_TRANSIT')`

### 2.6 `reviews`
- **Primary Key:** `review_id` (`REV-xxxxxx`)
- **Foreign Key:** `order_id UNIQUE REFERENCES orders(order_id)`
- **Constraints:** `rating BETWEEN 1 AND 5`

### 2.7 `disputes`
- **Primary Key:** `dispute_id` (`DSP-xxxxxx`)
- **Foreign Keys:** `order_id`, `seller_id`, `customer_id`
- **Constraints:** `disputed_amount > 0.0`, `status IN ('OPEN', 'UNDER_REVIEW', 'RESOLVED_BUYER_FAVOR', 'RESOLVED_SELLER_FAVOR', 'CHARGEBACK_LOST')`, `clawback_applied IN (0, 1)`

### 2.8 `order_settlements`
- **Primary Key:** `settlement_id`
- **Foreign Keys:** `order_id UNIQUE`, `seller_id`
- **Financial Balance:** `gross_amount = commission_amount + reserve_amount + net_seller_amount`

### 2.9 `payout_batches`
- **Primary Key:** `payout_id` (`PO-xxxxxx`)
- **Foreign Key:** `seller_id`
- **Constraints:** `payout_status IN ('SCHEDULED', 'PROCESSING', 'PAID', 'HELD', 'FAILED')`, `reconciliation_status IN ('MATCHED', 'DISCREPANCY', 'PENDING')`

### 2.10 `payout_lines`
- **Primary Key:** `line_id`
- **Foreign Keys:** `payout_id REFERENCES payout_batches(payout_id)`, `order_id REFERENCES orders(order_id)`
- **Balance:** `net_line_amount = order_amount - commission_deducted - reserve_deducted - dispute_deducted`

### 2.11 `anomalies_ground_truth`
- **Primary Key:** `anomaly_id` (`ANO-x-xxxx`)
- **Attributes:** `anomaly_type`, `entity_type`, `entity_id`, `description`, `severity`, `detected`, `created_at`
