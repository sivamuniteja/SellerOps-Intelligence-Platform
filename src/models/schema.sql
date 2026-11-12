-- ============================================================================
-- SellerOps Intelligence Platform - Relational Database Schema v2.0
-- Dialect: SQLite 3 with Strict Foreign Keys, CHECK Constraints & Integer Cents
-- ============================================================================

PRAGMA foreign_keys = ON;

-- 0. Schema Migrations History
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

-- 1. Sellers Entity
CREATE TABLE IF NOT EXISTS sellers (
    seller_id VARCHAR(32) PRIMARY KEY, -- SELL-000001
    name VARCHAR(128) NOT NULL,
    tier VARCHAR(32) NOT NULL CHECK(tier IN ('STANDARD', 'PREFERRED', 'ENTERPRISE', 'PROBATION', 'SUSPENDED')),
    status VARCHAR(32) NOT NULL CHECK(status IN ('ACTIVE', 'PROBATION', 'SUSPENDED', 'UNDER_REVIEW')),
    risk_score REAL NOT NULL CHECK(risk_score >= 0.0 AND risk_score <= 100.0),
    rating REAL NOT NULL CHECK(rating >= 1.0 AND rating <= 5.0),
    onboarding_date TEXT NOT NULL,
    bank_account_verified INTEGER NOT NULL DEFAULT 1 CHECK(bank_account_verified IN (0, 1)),
    country VARCHAR(32) NOT NULL DEFAULT 'USA',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 2. Seller Status Audit Events (Immutable)
CREATE TABLE IF NOT EXISTS seller_status_events (
    event_id VARCHAR(32) PRIMARY KEY, -- SSE-000001
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id) ON DELETE CASCADE,
    previous_status VARCHAR(32),
    new_status VARCHAR(32) NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 3. Customers Entity
CREATE TABLE IF NOT EXISTS customers (
    customer_id VARCHAR(32) PRIMARY KEY, -- CUST-000001
    name VARCHAR(128) NOT NULL,
    email VARCHAR(128) NOT NULL UNIQUE,
    city VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL,
    country VARCHAR(32) NOT NULL DEFAULT 'USA',
    created_at TEXT NOT NULL
);

-- 4. Product Listings Entity
CREATE TABLE IF NOT EXISTS listings (
    listing_id VARCHAR(64) PRIMARY KEY, -- LIST-{seller-id}-000001
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id) ON DELETE CASCADE,
    title VARCHAR(256) NOT NULL,
    category VARCHAR(64) NOT NULL,
    price_cents INTEGER NOT NULL CHECK(price_cents > 0),
    inventory_count INTEGER NOT NULL DEFAULT 0 CHECK(inventory_count >= 0),
    status VARCHAR(32) NOT NULL CHECK(status IN ('ACTIVE', 'OUT_OF_STOCK', 'SUSPENDED', 'ARCHIVED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 5. Commission Rules
CREATE TABLE IF NOT EXISTS commission_rules (
    rule_id VARCHAR(32) PRIMARY KEY, -- CR-000001
    category VARCHAR(64) NOT NULL,
    seller_tier VARCHAR(32) NOT NULL,
    base_rate_basis_points INTEGER NOT NULL CHECK(base_rate_basis_points >= 0), -- e.g. 800 = 8.00%
    min_commission_cents INTEGER NOT NULL DEFAULT 50 CHECK(min_commission_cents >= 0), -- $0.50 = 50
    fixed_fee_cents INTEGER NOT NULL DEFAULT 30 CHECK(fixed_fee_cents >= 0), -- $0.30 = 30
    effective_from TEXT NOT NULL,
    effective_to TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL
);

-- 6. Orders (Header Supporting Multi-Seller)
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(32) PRIMARY KEY, -- ORD-2026-000001
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    order_date TEXT NOT NULL,
    total_amount_cents INTEGER NOT NULL CHECK(total_amount_cents > 0),
    currency VARCHAR(8) NOT NULL DEFAULT 'INR',
    payment_method VARCHAR(32) NOT NULL,
    order_status VARCHAR(32) NOT NULL CHECK(order_status IN ('PLACED', 'CONFIRMED', 'PARTIALLY_SHIPPED', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 7. Order Lines (Multi-Seller Item Level)
CREATE TABLE IF NOT EXISTS order_lines (
    order_line_id VARCHAR(48) PRIMARY KEY, -- ORDLN-2026-000001-01
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    listing_id VARCHAR(64) NOT NULL REFERENCES listings(listing_id),
    line_number INTEGER NOT NULL CHECK(line_number > 0),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents > 0),
    gross_amount_cents INTEGER NOT NULL CHECK(gross_amount_cents > 0),
    line_status VARCHAR(32) NOT NULL CHECK(line_status IN ('PLACED', 'CONFIRMED', 'PARTIALLY_SHIPPED', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED')),
    created_at TEXT NOT NULL,
    UNIQUE(order_id, line_number)
);

-- 8. Fulfillments (Supporting Partial Fulfillment)
CREATE TABLE IF NOT EXISTS fulfillments (
    fulfillment_id VARCHAR(64) PRIMARY KEY, -- FUL-{order-line-id} or FUL-{order-line-id}-{part}
    order_line_id VARCHAR(48) NOT NULL REFERENCES order_lines(order_line_id) ON DELETE CASCADE,
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    carrier VARCHAR(64) NOT NULL,
    tracking_number VARCHAR(128) NOT NULL,
    quantity_fulfilled INTEGER NOT NULL CHECK(quantity_fulfilled > 0),
    dispatched_at TEXT,
    expected_delivery_at TEXT,
    delivered_at TEXT,
    sla_status VARCHAR(32) NOT NULL CHECK(sla_status IN ('ON_TIME', 'LATE', 'CANCELLED', 'IN_TRANSIT')),
    transit_days INTEGER CHECK(transit_days IS NULL OR transit_days >= 0),
    created_at TEXT NOT NULL
);

-- 9. Fulfillment Tracking Events (Immutable)
CREATE TABLE IF NOT EXISTS fulfillment_events (
    event_id VARCHAR(32) PRIMARY KEY, -- FLE-000001
    fulfillment_id VARCHAR(64) NOT NULL REFERENCES fulfillments(fulfillment_id) ON DELETE CASCADE,
    event_type VARCHAR(32) NOT NULL CHECK(event_type IN ('LABEL_CREATED', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'EXCEPTION', 'RETURNED_TO_SENDER')),
    event_timestamp TEXT NOT NULL,
    location VARCHAR(128),
    notes TEXT,
    created_at TEXT NOT NULL
);

-- 10. Customer Reviews
CREATE TABLE IF NOT EXISTS customer_reviews (
    review_id VARCHAR(32) PRIMARY KEY, -- REV-2026-000001
    order_line_id VARCHAR(48) UNIQUE NOT NULL REFERENCES order_lines(order_line_id) ON DELETE CASCADE,
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TEXT NOT NULL
);

-- 11. Disputes & Chargebacks
CREATE TABLE IF NOT EXISTS disputes (
    dispute_id VARCHAR(32) PRIMARY KEY, -- DSP-2026-000001
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    order_line_id VARCHAR(48) REFERENCES order_lines(order_line_id),
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    customer_id VARCHAR(32) NOT NULL REFERENCES customers(customer_id),
    dispute_date TEXT NOT NULL,
    dispute_reason VARCHAR(64) NOT NULL,
    disputed_amount_cents INTEGER NOT NULL CHECK(disputed_amount_cents > 0),
    status VARCHAR(32) NOT NULL CHECK(status IN ('OPEN', 'UNDER_REVIEW', 'RESOLVED_BUYER_FAVOR', 'RESOLVED_SELLER_FAVOR', 'CHARGEBACK_LOST')),
    resolution_date TEXT,
    clawback_applied INTEGER NOT NULL DEFAULT 0 CHECK(clawback_applied IN (0, 1)),
    created_at TEXT NOT NULL
);

-- 12. Dispute Lifecycle Events (Immutable)
CREATE TABLE IF NOT EXISTS dispute_events (
    event_id VARCHAR(32) PRIMARY KEY, -- DSE-000001
    dispute_id VARCHAR(32) NOT NULL REFERENCES disputes(dispute_id) ON DELETE CASCADE,
    previous_status VARCHAR(32),
    new_status VARCHAR(32) NOT NULL,
    actor VARCHAR(32) NOT NULL CHECK(actor IN ('BUYER', 'SELLER', 'ARBITRATOR', 'SYSTEM')),
    notes TEXT,
    created_at TEXT NOT NULL
);

-- 13. Commission Accounting Ledger (Immutable)
CREATE TABLE IF NOT EXISTS commission_ledger (
    entry_id VARCHAR(32) PRIMARY KEY, -- CML-000001
    order_line_id VARCHAR(48) UNIQUE NOT NULL REFERENCES order_lines(order_line_id),
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    rule_id VARCHAR(32) REFERENCES commission_rules(rule_id),
    gross_amount_cents INTEGER NOT NULL,
    rate_basis_points INTEGER NOT NULL,
    variable_fee_cents INTEGER NOT NULL,
    fixed_fee_cents INTEGER NOT NULL,
    total_commission_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

-- 14. Reserve Hold Ledger
CREATE TABLE IF NOT EXISTS reserve_ledger (
    entry_id VARCHAR(32) PRIMARY KEY, -- RSV-000001
    order_line_id VARCHAR(48) UNIQUE NOT NULL REFERENCES order_lines(order_line_id),
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    reserve_rate_basis_points INTEGER NOT NULL,
    reserve_amount_cents INTEGER NOT NULL,
    hold_days INTEGER NOT NULL,
    release_scheduled_date TEXT NOT NULL,
    status VARCHAR(32) NOT NULL CHECK(status IN ('HELD', 'RELEASED', 'FORFEITED')),
    released_at TEXT,
    created_at TEXT NOT NULL
);

-- 15. Refunds
CREATE TABLE IF NOT EXISTS refunds (
    refund_id VARCHAR(32) PRIMARY KEY, -- REF-2026-000001
    order_id VARCHAR(32) NOT NULL REFERENCES orders(order_id),
    order_line_id VARCHAR(48) REFERENCES order_lines(order_line_id),
    dispute_id VARCHAR(32) REFERENCES disputes(dispute_id),
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    refund_amount_cents INTEGER NOT NULL CHECK(refund_amount_cents > 0),
    refund_reason VARCHAR(64) NOT NULL,
    created_at TEXT NOT NULL
);

-- 16. Payout Batches
CREATE TABLE IF NOT EXISTS payouts (
    payout_id VARCHAR(32) PRIMARY KEY, -- PAYOUT-2026-000001
    seller_id VARCHAR(32) NOT NULL REFERENCES sellers(seller_id),
    batch_date TEXT NOT NULL,
    total_lines_count INTEGER NOT NULL CHECK(total_lines_count >= 0),
    gross_sales_cents INTEGER NOT NULL,
    total_commission_cents INTEGER NOT NULL,
    total_reserve_held_cents INTEGER NOT NULL,
    total_disputes_deducted_cents INTEGER NOT NULL DEFAULT 0,
    net_payout_amount_cents INTEGER NOT NULL,
    payout_status VARCHAR(32) NOT NULL CHECK(payout_status IN ('SCHEDULED', 'PROCESSING', 'PAID', 'HELD', 'FAILED')),
    reconciliation_status VARCHAR(32) NOT NULL CHECK(reconciliation_status IN ('MATCHED', 'DISCREPANCY', 'PENDING')),
    created_at TEXT NOT NULL
);

-- 17. Payout Line Items
CREATE TABLE IF NOT EXISTS payout_lines (
    line_id VARCHAR(48) PRIMARY KEY, -- PLN-PAYOUT-2026-000001-01
    payout_id VARCHAR(32) NOT NULL REFERENCES payouts(payout_id) ON DELETE CASCADE,
    order_line_id VARCHAR(48) NOT NULL REFERENCES order_lines(order_line_id),
    gross_amount_cents INTEGER NOT NULL,
    commission_deducted_cents INTEGER NOT NULL,
    reserve_deducted_cents INTEGER NOT NULL,
    dispute_deducted_cents INTEGER NOT NULL DEFAULT 0,
    net_line_amount_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

-- 18. Payout Lifecycle Events (Immutable)
CREATE TABLE IF NOT EXISTS payout_events (
    event_id VARCHAR(32) PRIMARY KEY, -- POE-000001
    payout_id VARCHAR(32) NOT NULL REFERENCES payouts(payout_id) ON DELETE CASCADE,
    previous_status VARCHAR(32),
    new_status VARCHAR(32) NOT NULL,
    gateway_reference VARCHAR(128),
    notes TEXT,
    created_at TEXT NOT NULL
);

-- 19. Ground Truth Anomaly Registry
CREATE TABLE IF NOT EXISTS ground_truth (
    anomaly_id VARCHAR(32) PRIMARY KEY, -- ANO-1-0001
    anomaly_type VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(16) NOT NULL CHECK(severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    detected INTEGER NOT NULL DEFAULT 0 CHECK(detected IN (0, 1)),
    created_at TEXT NOT NULL
);

-- ============================================================================
-- Indexes for Sub-Second Query Performance Across Millions of Records
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_sellers_tier ON sellers(tier);
CREATE INDEX IF NOT EXISTS idx_sellers_status ON sellers(status);
CREATE INDEX IF NOT EXISTS idx_listings_seller ON listings(seller_id);
CREATE INDEX IF NOT EXISTS idx_listings_category ON listings(category);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status);
CREATE INDEX IF NOT EXISTS idx_order_lines_order ON order_lines(order_id);
CREATE INDEX IF NOT EXISTS idx_order_lines_seller ON order_lines(seller_id);
CREATE INDEX IF NOT EXISTS idx_order_lines_listing ON order_lines(listing_id);
CREATE INDEX IF NOT EXISTS idx_fulfillments_order_line ON fulfillments(order_line_id);
CREATE INDEX IF NOT EXISTS idx_fulfillments_sla ON fulfillments(sla_status);
CREATE INDEX IF NOT EXISTS idx_disputes_seller_date ON disputes(seller_id, dispute_date);
CREATE INDEX IF NOT EXISTS idx_disputes_order ON disputes(order_id);
CREATE INDEX IF NOT EXISTS idx_payouts_seller_date ON payouts(seller_id, batch_date);
CREATE INDEX IF NOT EXISTS idx_payout_lines_payout ON payout_lines(payout_id);
CREATE INDEX IF NOT EXISTS idx_payout_lines_order_line ON payout_lines(order_line_id);
CREATE INDEX IF NOT EXISTS idx_commission_rules_cat_tier ON commission_rules(category, seller_tier, effective_from, effective_to);
CREATE INDEX IF NOT EXISTS idx_ground_truth_type ON ground_truth(anomaly_type);
