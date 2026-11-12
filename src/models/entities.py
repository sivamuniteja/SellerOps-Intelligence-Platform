"""Domain entities and Pydantic validation models for SellerOps Intelligence Platform."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


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


class Seller(BaseModel):
    seller_id: str = Field(..., pattern=r"^SLR-\d{5}$")
    name: str
    tier: SellerTier
    status: SellerStatus
    risk_score: float = Field(..., ge=0.0, le=100.0)
    rating: float = Field(..., ge=1.0, le=5.0)
    onboarding_date: str
    bank_account_verified: int = 1
    country: str = "USA"
    created_at: str


class Customer(BaseModel):
    customer_id: str = Field(..., pattern=r"^CST-\d{5}$")
    name: str
    email: str
    city: str
    state: str
    country: str = "USA"
    created_at: str


class Listing(BaseModel):
    listing_id: str = Field(..., pattern=r"^LST-\d{6}$")
    seller_id: str = Field(..., pattern=r"^SLR-\d{5}$")
    title: str
    category: str
    price: float = Field(..., gt=0.0)
    inventory_count: int = Field(default=0, ge=0)
    status: str
    created_at: str


class Order(BaseModel):
    order_id: str = Field(..., pattern=r"^ORD-\d{6}$")
    customer_id: str = Field(..., pattern=r"^CST-\d{5}$")
    seller_id: str = Field(..., pattern=r"^SLR-\d{5}$")
    listing_id: str = Field(..., pattern=r"^LST-\d{6}$")
    order_date: str
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0.0)
    gross_amount: float = Field(..., gt=0.0)
    currency: str = "USD"
    payment_method: str
    order_status: OrderStatus


class Fulfillment(BaseModel):
    fulfillment_id: str = Field(..., pattern=r"^FLF-\d{6}$")
    order_id: str = Field(..., pattern=r"^ORD-\d{6}$")
    carrier: str
    tracking_number: str
    dispatched_at: Optional[str] = None
    expected_delivery_at: Optional[str] = None
    delivered_at: Optional[str] = None
    sla_status: SLAStatus
    transit_days: Optional[int] = None


class Review(BaseModel):
    review_id: str = Field(..., pattern=r"^REV-\d{6}$")
    order_id: str = Field(..., pattern=r"^ORD-\d{6}$")
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    created_at: str


class Dispute(BaseModel):
    dispute_id: str = Field(..., pattern=r"^DSP-\d{6}$")
    order_id: str = Field(..., pattern=r"^ORD-\d{6}$")
    seller_id: str = Field(..., pattern=r"^SLR-\d{5}$")
    customer_id: str = Field(..., pattern=r"^CST-\d{5}$")
    dispute_date: str
    dispute_reason: str
    disputed_amount: float = Field(..., gt=0.0)
    status: DisputeStatus
    resolution_date: Optional[str] = None
    clawback_applied: int = 0


class OrderSettlement(BaseModel):
    settlement_id: str
    order_id: str
    seller_id: str
    gross_amount: float
    commission_rate: float
    commission_amount: float
    reserve_rate: float
    reserve_amount: float
    reserve_release_date: str
    reserve_released: int = 0
    net_seller_amount: float
    is_eligible_for_payout: int = 0
    created_at: str


class PayoutBatch(BaseModel):
    payout_id: str = Field(..., pattern=r"^PO-\d{6}$")
    seller_id: str = Field(..., pattern=r"^SLR-\d{5}$")
    batch_date: str
    total_orders_count: int = Field(..., ge=0)
    gross_sales: float
    total_commission: float
    total_reserve_held: float
    total_disputes_deducted: float = 0.0
    net_payout_amount: float
    payout_status: PayoutStatus
    reconciliation_status: ReconciliationStatus
    created_at: str


class PayoutLine(BaseModel):
    line_id: str
    payout_id: str
    order_id: str
    order_amount: float
    commission_deducted: float
    reserve_deducted: float
    dispute_deducted: float = 0.0
    net_line_amount: float
    created_at: str


class AnomalyGroundTruth(BaseModel):
    anomaly_id: str
    anomaly_type: str
    entity_type: str
    entity_id: str
    description: str
    severity: str
    detected: int = 0
    created_at: str
