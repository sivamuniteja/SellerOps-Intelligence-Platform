"""Domain entities and Pydantic validation models for SellerOps Intelligence Platform.

Enforces:
- Exact ID regex formats: SELL-000001, LIST-{seller_id}-000001, ORD-2026-000001, FUL-{order_line_id}, DSP-2026-000001, PAYOUT-2026-000001
- Integer cents/paise for all currency values.
- Multi-seller order lines & partial fulfillments.
- Immutable event logs.
"""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional, List, Union
from pydantic import BaseModel, Field, field_validator


def cents_to_decimal(cents: int) -> Decimal:
    """Convert integer cents/paise to exact Decimal currency."""
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal_to_cents(amount: Union[float, Decimal, str]) -> int:
    """Convert decimal or float amount to exact integer cents."""
    dec = Decimal(str(amount))
    return int((dec * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class SellerTier(str, Enum):
    STANDARD = "STANDARD"
    PREFERRED = "PREFERRED"
    ENTERPRISE = "ENTERPRISE"
    PROBATION = "PROBATION"
    SUSPENDED = "SUSPENDED"


class SellerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PROBATION = "PROBATION"
    SUSPENDED = "SUSPENDED"
    UNDER_REVIEW = "UNDER_REVIEW"


class OrderStatus(str, Enum):
    PLACED = "PLACED"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_SHIPPED = "PARTIALLY_SHIPPED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


class LineStatus(str, Enum):
    PLACED = "PLACED"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_SHIPPED = "PARTIALLY_SHIPPED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


class SLAStatus(str, Enum):
    ON_TIME = "ON_TIME"
    LATE = "LATE"
    CANCELLED = "CANCELLED"
    IN_TRANSIT = "IN_TRANSIT"


class DisputeStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED_BUYER_FAVOR = "RESOLVED_BUYER_FAVOR"
    RESOLVED_SELLER_FAVOR = "RESOLVED_SELLER_FAVOR"
    CHARGEBACK_LOST = "CHARGEBACK_LOST"


class PayoutStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    HELD = "HELD"
    FAILED = "FAILED"


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    DISCREPANCY = "DISCREPANCY"
    PENDING = "PENDING"


# 1. Seller Entity
class Seller(BaseModel):
    seller_id: str = Field(..., pattern=r"^SELL-\d{6}$")
    name: str
    tier: SellerTier
    status: SellerStatus
    risk_score: float = Field(..., ge=0.0, le=100.0)
    rating: float = Field(..., ge=1.0, le=5.0)
    onboarding_date: str
    bank_account_verified: int = 1
    country: str = "USA"
    created_at: str
    updated_at: str


# 2. Seller Status Event (Immutable)
class SellerStatusEvent(BaseModel):
    event_id: str = Field(..., pattern=r"^SSE-\d{6}$")
    seller_id: str = Field(..., pattern=r"^SELL-\d{6}$")
    previous_status: Optional[str] = None
    new_status: str
    reason: str
    created_at: str


# 3. Customer Entity
class Customer(BaseModel):
    customer_id: str = Field(..., pattern=r"^CUST-\d{6}$")
    name: str
    email: str
    city: str
    state: str
    country: str = "USA"
    created_at: str


# 4. Product Listing Entity
class ProductListing(BaseModel):
    listing_id: str = Field(..., pattern=r"^LIST-SELL-\d{6}-\d{6}$")
    seller_id: str = Field(..., pattern=r"^SELL-\d{6}$")
    title: str
    category: str
    price_cents: int = Field(..., gt=0)
    inventory_count: int = Field(default=0, ge=0)
    status: str
    created_at: str
    updated_at: str

    @property
    def price_dollars(self) -> Decimal:
        return cents_to_decimal(self.price_cents)


# 5. Commission Rule
class CommissionRule(BaseModel):
    rule_id: str = Field(..., pattern=r"^CR-\d{6}$")
    category: str
    seller_tier: str
    base_rate_basis_points: int = Field(..., ge=0)
    min_commission_cents: int = 50
    fixed_fee_cents: int = 30
    effective_from: str
    effective_to: str
    is_active: int = 1
    created_at: str


# 6. Order (Header Supporting Multi-Seller)
class Order(BaseModel):
    order_id: str = Field(..., pattern=r"^ORD-\d{4}-\d{6}$")
    customer_id: str = Field(..., pattern=r"^CUST-\d{6}$")
    order_date: str
    total_amount_cents: int = Field(..., gt=0)
    currency: str = "USD"
    payment_method: str
    order_status: OrderStatus
    created_at: str
    updated_at: str

    @property
    def total_amount_dollars(self) -> Decimal:
        return cents_to_decimal(self.total_amount_cents)


# 7. Order Line (Item Level, Multi-Seller)
class OrderLine(BaseModel):
    order_line_id: str = Field(..., pattern=r"^ORDLN-\d{4}-\d{6}-\d{2}$")
    order_id: str = Field(..., pattern=r"^ORD-\d{4}-\d{6}$")
    seller_id: str = Field(..., pattern=r"^SELL-\d{6}$")
    listing_id: str = Field(..., pattern=r"^LIST-SELL-\d{6}-\d{6}$")
    line_number: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)
    unit_price_cents: int = Field(..., gt=0)
    gross_amount_cents: int = Field(..., gt=0)
    line_status: LineStatus
    created_at: str

    @property
    def gross_amount_dollars(self) -> Decimal:
        return cents_to_decimal(self.gross_amount_cents)


# 8. Fulfillment (Supporting Partial Fulfillment)
class Fulfillment(BaseModel):
    fulfillment_id: str = Field(..., pattern=r"^FUL-ORDLN-\d{4}-\d{6}-\d{2}(-\d{2})?$")
    order_line_id: str = Field(..., pattern=r"^ORDLN-\d{4}-\d{6}-\d{2}$")
    order_id: str = Field(..., pattern=r"^ORD-\d{4}-\d{6}$")
    seller_id: str = Field(..., pattern=r"^SELL-\d{6}$")
    carrier: str
    tracking_number: str
    quantity_fulfilled: int = Field(..., gt=0)
    dispatched_at: Optional[str] = None
    expected_delivery_at: Optional[str] = None
    delivered_at: Optional[str] = None
    sla_status: SLAStatus
    transit_days: Optional[int] = None
    created_at: str


# 9. Fulfillment Tracking Event (Immutable)
class FulfillmentEvent(BaseModel):
    event_id: str = Field(..., pattern=r"^FLE-\d{6}$")
    fulfillment_id: str
    event_type: str
    event_timestamp: str
    location: Optional[str] = None
    notes: Optional[str] = None
    created_at: str


# 10. Customer Review
class CustomerReview(BaseModel):
    review_id: str = Field(..., pattern=r"^REV-\d{4}-\d{6}$")
    order_line_id: str = Field(..., pattern=r"^ORDLN-\d{4}-\d{6}-\d{2}$")
    order_id: str = Field(..., pattern=r"^ORD-\d{4}-\d{6}$")
    seller_id: str = Field(..., pattern=r"^SELL-\d{6}$")
    customer_id: str = Field(..., pattern=r"^CUST-\d{6}$")
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    created_at: str


# 11. Dispute Entity
class Dispute(BaseModel):
    dispute_id: str = Field(..., pattern=r"^DSP-\d{4}-\d{6}$")
    order_id: str = Field(..., pattern=r"^ORD-\d{4}-\d{6}$")
    order_line_id: Optional[str] = None
    seller_id: str = Field(..., pattern=r"^SELL-\d{6}$")
    customer_id: str = Field(..., pattern=r"^CUST-\d{6}$")
    dispute_date: str
    dispute_reason: str
    disputed_amount_cents: int = Field(..., gt=0)
    status: DisputeStatus
    resolution_date: Optional[str] = None
    clawback_applied: int = 0
    created_at: str


# 12. Dispute Event (Immutable)
class DisputeEvent(BaseModel):
    event_id: str = Field(..., pattern=r"^DSE-\d{6}$")
    dispute_id: str = Field(..., pattern=r"^DSP-\d{4}-\d{6}$")
    previous_status: Optional[str] = None
    new_status: str
    actor: str
    notes: Optional[str] = None
    created_at: str


# 13. Commission Ledger Entry (Immutable)
class CommissionLedger(BaseModel):
    entry_id: str = Field(..., pattern=r"^CML-\d{6}$")
    order_line_id: str
    seller_id: str
    rule_id: Optional[str] = None
    gross_amount_cents: int
    rate_basis_points: int
    variable_fee_cents: int
    fixed_fee_cents: int
    total_commission_cents: int
    created_at: str


# 14. Reserve Ledger Entry
class ReserveLedger(BaseModel):
    entry_id: str = Field(..., pattern=r"^RSV-\d{6}$")
    order_line_id: str
    seller_id: str
    reserve_rate_basis_points: int
    reserve_amount_cents: int
    hold_days: int
    release_scheduled_date: str
    status: str
    released_at: Optional[str] = None
    created_at: str


# 15. Refund Entity
class Refund(BaseModel):
    refund_id: str = Field(..., pattern=r"^REF-\d{4}-\d{6}$")
    order_id: str
    order_line_id: Optional[str] = None
    dispute_id: Optional[str] = None
    seller_id: str
    refund_amount_cents: int = Field(..., gt=0)
    refund_reason: str
    created_at: str


# 16. Payout Batch
class Payout(BaseModel):
    payout_id: str = Field(..., pattern=r"^PAYOUT-\d{4}-\d{6}$")
    seller_id: str = Field(..., pattern=r"^SELL-\d{6}$")
    batch_date: str
    total_lines_count: int = Field(..., ge=0)
    gross_sales_cents: int
    total_commission_cents: int
    total_reserve_held_cents: int
    total_disputes_deducted_cents: int = 0
    net_payout_amount_cents: int
    payout_status: PayoutStatus
    reconciliation_status: ReconciliationStatus
    created_at: str


# 17. Payout Line
class PayoutLine(BaseModel):
    line_id: str = Field(..., pattern=r"^PLN-PAYOUT-\d{4}-\d{6}-\d{2}$")
    payout_id: str = Field(..., pattern=r"^PAYOUT-\d{4}-\d{6}$")
    order_line_id: str = Field(..., pattern=r"^ORDLN-\d{4}-\d{6}-\d{2}$")
    gross_amount_cents: int
    commission_deducted_cents: int
    reserve_deducted_cents: int
    dispute_deducted_cents: int = 0
    net_line_amount_cents: int
    created_at: str


# 18. Payout Event (Immutable)
class PayoutEvent(BaseModel):
    event_id: str = Field(..., pattern=r"^POE-\d{6}$")
    payout_id: str = Field(..., pattern=r"^PAYOUT-\d{4}-\d{6}$")
    previous_status: Optional[str] = None
    new_status: str
    gateway_reference: Optional[str] = None
    notes: Optional[str] = None
    created_at: str


# 19. Ground Truth Anomaly
class GroundTruth(BaseModel):
    anomaly_id: str
    anomaly_type: str
    entity_type: str
    entity_id: str
    description: str
    severity: str
    detected: int = 0
    created_at: str
