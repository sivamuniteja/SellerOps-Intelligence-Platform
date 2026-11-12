-- ============================================================================
-- SellerOps Intelligence Platform - Relational Database Schema
-- Dialect: SQLite 3 with Foreign Keys & Strict Typing
-- ============================================================================

PRAGMA foreign_keys = ON;

-- 1. Sellers Table
CREATE TABLE IF NOT EXISTS sellers (
    seller_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    tier VARCHAR(32) NOT NULL CHECK(tier IN ('STANDARD', 'PREFERRED', 'ENTERPRISE', 'PROBATION', 'SUSPENDED')),
    status VARCHAR(32) NOT NULL CHECK(status IN ('ACTIVE', 'PROBATION', 'SUSPENDED', 'UNDER_REVIEW')),
    risk_score REAL NOT NULL CHECK(risk_score >= 0.0 AND risk_score <= 100.0),
    rating REAL NOT NULL CHECK(rating >= 1.0 AND rating <= 5.0),
    onboarding_date TEXT NOT NULL,
    bank_account_verified INTEGER NOT NULL DEFAULT 1 CHECK(bank_account_verified IN (0, 1)),
    country VARCHAR(32) NOT NULL DEFAULT 'USA',
    created_at TEXT NOT NULL
);

-- 2. Customers Table
CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    email VARCHAR(128) NOT NULL,
    city VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL,
    country VARCHAR(32) NOT NULL DEFAULT 'USA',
    created_at TEXT NOT NULL
);

-- 3. Product Listings Table
CREATE TABLE IF NOT EXISTS listings (
    listing_id VARCHAR(32) PRIMARY KEY,
    seller_id VARCHAR(32) NOT NULL,
    title VARCHAR(256) NOT NULL,
    category VARCHAR(64) NOT NULL,
    price REAL NOT NULL CHECK(price > 0.0),
    inventory_count INTEGER NOT NULL DEFAULT 0 CHECK(inventory_count >= 0),
    status VARCHAR(32) NOT NULL CHECK(status IN ('ACTIVE', 'OUT_OF_STOCK', 'SUSPENDED', 'ARCHIVED')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (seller_id) REFERENCES sellers(seller_id) ON DELETE CASCADE
);

-- 4. Orders Table
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(32) PRIMARY KEY,
    customer_id VARCHAR(32) NOT NULL,
    seller_id VARCHAR(32) NOT NULL,
    listing_id VARCHAR(32) NOT NULL,
    order_date TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price > 0.0),
    gross_amount REAL NOT NULL CHECK(gross_amount > 0.0),
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    payment_method VARCHAR(32) NOT NULL,
    order_status VARCHAR(32) NOT NULL CHECK(order_status IN ('PLACED', 'CONFIRMED', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED')),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (seller_id) REFERENCES sellers(seller_id),
    FOREIGN KEY (listing_id) REFERENCES listings(listing_id)
);

-- 5. Fulfillments Table
CREATE TABLE IF NOT EXISTS fulfillments (
    fulfillment_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) UNIQUE NOT NULL,
    carrier VARCHAR(64) NOT NULL,
    tracking_number VARCHAR(128) NOT NULL,
    dispatched_at TEXT,
    expected_delivery_at TEXT,
    delivered_at TEXT,
    sla_status VARCHAR(32) NOT NULL CHECK(sla_status IN ('ON_TIME', 'LATE', 'CANCELLED', 'IN_TRANSIT')),
    transit_days INTEGER CHECK(transit_days IS NULL OR transit_days >= 0),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- 6. Customer Reviews Table
CREATE TABLE IF NOT EXISTS reviews (
    review_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) UNIQUE NOT NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
);

-- 7. Disputes & Chargebacks Table
CREATE TABLE IF NOT EXISTS disputes (
    dispute_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) NOT NULL,
    seller_id VARCHAR(32) NOT NULL,
    customer_id VARCHAR(32) NOT NULL,
    dispute_date TEXT NOT NULL,
    dispute_reason VARCHAR(64) NOT NULL,
    disputed_amount REAL NOT NULL CHECK(disputed_amount > 0.0),
    status VARCHAR(32) NOT NULL CHECK(status IN ('OPEN', 'UNDER_REVIEW', 'RESOLVED_BUYER_FAVOR', 'RESOLVED_SELLER_FAVOR', 'CHARGEBACK_LOST')),
    resolution_date TEXT,
    clawback_applied INTEGER NOT NULL DEFAULT 0 CHECK(clawback_applied IN (0, 1)),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (seller_id) REFERENCES sellers(seller_id),
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- 8. Order Settlements (Commission & Reserve Accounting)
CREATE TABLE IF NOT EXISTS order_settlements (
    settlement_id VARCHAR(32) PRIMARY KEY,
    order_id VARCHAR(32) UNIQUE NOT NULL,
    seller_id VARCHAR(32) NOT NULL,
    gross_amount REAL NOT NULL,
    commission_rate REAL NOT NULL,
    commission_amount REAL NOT NULL,
    reserve_rate REAL NOT NULL,
    reserve_amount REAL NOT NULL,
    reserve_release_date TEXT NOT NULL,
    reserve_released INTEGER NOT NULL DEFAULT 0 CHECK(reserve_released IN (0, 1)),
    net_seller_amount REAL NOT NULL,
    is_eligible_for_payout INTEGER NOT NULL DEFAULT 0 CHECK(is_eligible_for_payout IN (0, 1)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (seller_id) REFERENCES sellers(seller_id)
);

-- 9. Payout Batches
CREATE TABLE IF NOT EXISTS payout_batches (
    payout_id VARCHAR(32) PRIMARY KEY,
    seller_id VARCHAR(32) NOT NULL,
    batch_date TEXT NOT NULL,
    total_orders_count INTEGER NOT NULL CHECK(total_orders_count >= 0),
    gross_sales REAL NOT NULL,
    total_commission REAL NOT NULL,
    total_reserve_held REAL NOT NULL,
    total_disputes_deducted REAL NOT NULL DEFAULT 0.0,
    net_payout_amount REAL NOT NULL,
    payout_status VARCHAR(32) NOT NULL CHECK(payout_status IN ('SCHEDULED', 'PROCESSING', 'PAID', 'HELD', 'FAILED')),
    reconciliation_status VARCHAR(32) NOT NULL CHECK(reconciliation_status IN ('MATCHED', 'DISCREPANCY', 'PENDING')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (seller_id) REFERENCES sellers(seller_id)
);

-- 10. Payout Line Items
CREATE TABLE IF NOT EXISTS payout_lines (
    line_id VARCHAR(32) PRIMARY KEY,
    payout_id VARCHAR(32) NOT NULL,
    order_id VARCHAR(32) NOT NULL,
    order_amount REAL NOT NULL,
    commission_deducted REAL NOT NULL,
    reserve_deducted REAL NOT NULL,
    dispute_deducted REAL NOT NULL DEFAULT 0.0,
    net_line_amount REAL NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (payout_id) REFERENCES payout_batches(payout_id) ON DELETE CASCADE,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- 11. Ground-Truth Anomaly Registry
CREATE TABLE IF NOT EXISTS anomalies_ground_truth (
    anomaly_id VARCHAR(32) PRIMARY KEY,
    anomaly_type VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    entity_id VARCHAR(32) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(16) NOT NULL CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    detected INTEGER NOT NULL DEFAULT 0 CHECK(detected IN (0, 1)),
    created_at TEXT NOT NULL
);

-- ============================================================================
-- Indexes for Sub-Second Analytics Queries
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_sellers_tier_status ON sellers(tier, status);
CREATE INDEX IF NOT EXISTS idx_listings_seller ON listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category);
CREATE INDEX IF NOT EXISTS idx_orders_seller_date ON orders(seller_id, order_date);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status);
CREATE INDEX IF NOT EXISTS idx_fulfillments_order ON fulfillments(order_id);
CREATE INDEX IF NOT EXISTS idx_fulfillments_sla ON fulfillments(sla_status);
CREATE INDEX IF NOT EXISTS idx_disputes_seller_date ON disputes(seller_id, dispute_date);
CREATE INDEX IF NOT EXISTS idx_settlements_seller ON order_settlements(seller_id, is_eligible_for_payout);
CREATE INDEX IF NOT EXISTS idx_payout_batches_seller ON payout_batches(seller_id, batch_date);
CREATE INDEX IF NOT EXISTS idx_payout_lines_payout ON payout_lines(payout_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies_ground_truth(anomaly_type);
