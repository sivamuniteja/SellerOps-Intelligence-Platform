# Marketplace Business Rules & Financial Policy
**SellerOps Intelligence Platform – Production Architecture**

---

## 🇮🇳 Global INR Currency Standard

All platform accounting, ledgers, fee calculations, reserve holds, and payout disbursements strictly operate in **Indian Rupees (INR – ₹)**:
- **Currency Code:** `INR`
- **Currency Symbol:** `₹`
- **Minor Unit:** `paise` (1 Rupee = 100 paise; 1 minor unit = 1/100th of main currency unit).
- **Exact Integer Storage:** To guarantee zero binary floating-point drift, database records store amounts as integer paise (`_cents` columns).
- **Decimal Rounding:** All fractional calculations use Python `Decimal` with `ROUND_HALF_UP`.
- **Display Notation:** Indian numbering grouping (`en_IN`: Lakhs and Crores e.g., `₹1,03,86,130.23`, `₹12.50 L`, `₹1.04 Cr`).

---

## 1. Commission & Fee Calculation Policy (Engine A)

Platform take-rates are governed by product category schedules, adjusted by seller tier volume discounts, with fixed handling charges and effective-dated validity windows.

### 1.1 Category Base Rates
- **Electronics:** 8.0% (800 bps)
- **Fashion & Apparel:** 15.0% (1500 bps)
- **Home & Kitchen:** 12.0% (1200 bps)
- **Beauty & Personal Care:** 14.0% (1400 bps)
- **Sports & Outdoors:** 10.0% (1000 bps)
- **Books & Media:** 15.0% (1500 bps)
- **Automotive:** 10.0% (1000 bps)
- **Health & Wellness:** 12.5% (1250 bps)

### 1.2 Seller Tier Discounts
- **ENTERPRISE** (GMV $\ge ₹50,000$): -2.0% discount (-200 bps).
- **PREFERRED** (GMV $\ge ₹10,000$): -1.0% discount (-100 bps).
- **STANDARD**: Base category rate.
- **PROBATION**: +2.0% risk surcharge (+200 bps).

### 1.3 Fee Formula & Precision
All calculations use exact integer paise:
$$\text{Effective Rate} = \max(0.01, \text{Base Rate} - \text{Tier Discount})$$
$$\text{Variable Fee Paise} = \max\left(\left\lfloor \frac{\text{Gross Paise} \times \text{Rate Bps}}{10000} + 0.5 \right\rfloor, \text{Min Fee Paise}\right)$$
$$\text{Total Commission Paise} = \text{Variable Fee Paise} + \text{Fixed Fee Paise (30 Paise = ₹0.30)}$$

### 1.4 Deduplication & Ledger Immutability
- Every order line commission calculation is recorded into `commission_ledger`.
- Duplicate calculations for the same `order_line_id` are strictly prevented by raising `DuplicateCommissionError`.
- Commission entries cannot be modified or deleted once recorded.

---

## 2. Risk-Based Rolling Reserve Policy (Engine B)

To protect buyers and the marketplace from chargeback insolvency and fraud, a rolling reserve is withheld from every completed order line:

| Seller Tier | Base Reserve Rate | Base Hold Window | High Risk Surcharge (> 65 Score) |
| :--- | :--- | :--- | :--- |
| **ENTERPRISE** | 5.0% (500 bps) | 7 Days | +5.0% / +7 Days |
| **PREFERRED** | 8.0% (800 bps) | 14 Days | +5.0% / +7 Days |
| **STANDARD** | 10.0% (1000 bps) | 14 Days | +5.0% / +7 Days |
| **PROBATION** | 20.0% (2000 bps) | 30 Days | +5.0% / +7 Days |
| **SUSPENDED** | 100.0% (10000 bps) | 90 Days | Indefinite review |

### 2.1 Hold & Release Timing
$$\text{Hold Release Date} = \text{Delivery Date} + \text{Hold Duration}$$
- **Premature Release Protection:** The system strictly prohibits releasing held reserves prior to $\text{Hold Release Date}$, raising `PrematureReserveReleaseError`.
- **Suspension Protection:** Any release attempted for a seller with `status = 'SUSPENDED'` is blocked with `SuspendedSellerReleaseError`.
- **Reserve Balance Equation:**
  $$\text{Remaining Reserve} = \text{Total Reserve Held} - \text{Total Reserve Released}$$

---

## 3. Fulfillment Lifecycle & SLA Policy (Engine C)

### 3.1 Finite Lifecycle State Transitions
The platform strictly enforces the following state transitions:
$$\text{ORDER\_RECEIVED} \rightarrow \text{PROCESSING} \rightarrow \text{PACKED} \rightarrow \text{SHIPPED} \rightarrow \text{OUT\_FOR\_DELIVERY} \rightarrow \text{DELIVERED}$$
- **Cancellation:** Permitted only from early states (`ORDER_RECEIVED`, `PROCESSING`, `PACKED`). Direct cancellation after shipment is illegal.
- **Returns:** Permitted exclusively from `DELIVERED`.
- **Illegal Transitions:** Any out-of-order transition raises `InvalidFulfillmentTransitionError`.

### 3.2 Dispatch SLA & Delay Tracking
- **Standard Dispatch Window:** 48 hours from order creation.
- **Shipment Delay Hours:** $\max(0, \text{Actual Shipment} - \text{Expected Shipment})$.
- **Delivery Delay Hours:** $\max(0, \text{Actual Delivery} - \text{Expected Delivery})$.
- **SLA Breach Condition:** Marked `LATE` / `sla_breached = 1` if dispatch exceeds 48 hours or transit exceeds estimated delivery window.

### 3.3 Event Preservation
Every state change writes an immutable audit record to `fulfillment_events` (`event_id`, `fulfillment_id`, `event_type`, `previous_status`, `new_status`, `occurred_at`).

---

## 4. Payout Engine & Settlement Rules (Engine D)

### 4.1 Net Payable Formula
Payout disbursements are governed by exact arithmetic:
$$\text{Net Payable} = \text{Gross Sales} - \text{Commission} - \text{Refunds} - \text{Finalized Disputes} - \text{Reserve Held} + \text{Eligible Reserve Releases}$$

### 4.2 Overpayment & Double Deduction Protections
- **Duplicate Payout Line Prevention:** Each order line can be disbursed in at most one payout batch. Re-disbursement attempts raise `DuplicatePayoutLineError`.
- **Double Deduction Prevention:** Finalized dispute chargebacks and refund deductions are tracked by ID; duplicate deductions raise `DoubleDeductionError`.
- **Minimum Payout Threshold:** Minimum disbursement batch amount is **₹25.00** (2,500 paise). If net payable is below this threshold, payout status is held as `HELD`.
- **Negative Balances:** If deductions exceed gross earnings, net payable cannot be disbursed as cash; the balance is set to `HELD` and carried forward.

### 4.3 Payout Lifecycle States
- `PENDING` $\rightarrow$ `ELIGIBLE`, `HELD`
- `ELIGIBLE` $\rightarrow$ `PROCESSING`, `HELD`
- `HELD` $\rightarrow$ `ELIGIBLE`, `PROCESSING`, `FAILED`
- `PROCESSING` $\rightarrow$ `PAID`, `FAILED`
- `FAILED` $\rightarrow$ `ELIGIBLE`, `HELD`, `PROCESSING`
- `PAID` is terminal.

---

## 5. Official Financial Verification Fixtures (Section 5)

All 5 mandatory test fixtures are verified with exact integer arithmetic:

### Fixture 1: Standard Illustrative Payout Batch
- Gross sales: ₹1,00,000.00 (10,000,000 paise) across delivered orders.
- Commission: ₹12,000.00 (1,200,000 paise).
- Reserve held (10%): ₹10,000.00 (1,000,000 paise).
- Matured reserve released: ₹5,000.00 (500,000 paise).
- Finalized lost dispute: ₹2,000.00 (200,000 paise).
- **Net Payable:** ₹1,00,000 - ₹12,000 - ₹10,000 + ₹5,000 - ₹2,000 = **₹81,000.00** (8,100,000 paise).

### Fixture 2: Reserve Release Idempotency
- Reserve amount ₹5,000.00 released on maturity date $T$.
- Re-running settlement on $T+1$ does NOT re-credit the ₹5,000.00 release.
- Remaining reserve correctly drops to ₹0.00.

### Fixture 3: Partial Refund Deduction
- Order line gross: ₹1,000.00 (100,000 paise).
- Commission (10% + ₹0.30): ₹100.30 (10,030 paise).
- Reserve (10%): ₹100.00 (10,000 paise).
- Partial refund issued: ₹300.00 (30,000 paise).
- Adjusted gross: ₹700.00; Adjusted commission: ₹70.30; Adjusted reserve: ₹70.00.
- **Net Payable to Seller:** ₹700.00 - ₹70.30 - ₹70.00 = **₹559.70** (55,970 paise).

### Fixture 4: Multi-Seller Order Payout Separation
- Multi-seller order ORD-01: Line 1 (Seller A, ₹600.00), Line 2 (Seller B, ₹400.00). Total: ₹1,000.00.
- Seller A batch: Gross ₹600.00; Commission ₹60.30; Reserve ₹60.00. Net: **₹479.70**.
- Seller B batch: Gross ₹400.00; Commission ₹40.30; Reserve ₹40.00. Net: **₹319.70**.
- Zero cross-contamination between Seller A and Seller B ledgers.

### Fixture 5: Dispute Chargeback Deducted Exactly Once
- Chargeback DSP-01 lost for ₹1,500.00.
- Payout Batch 1 deducts ₹1,500.00; `clawback_applied` set to 1.
- Payout Batch 2 recognizes existing deduction and deducts ₹0.00.

---

## 6. Seller Performance Metrics & Denominators (Engine E)

All performance indicators are computed from source records with explicit denominators:

| Metric | Numerator | Denominator | SLA Breach Threshold |
| :--- | :--- | :--- | :--- |
| **Fulfillment Rate** | Delivered Order Lines | Total Order Lines | $< 95.0\%$ |
| **Late Shipment Rate (LSR)** | Late Dispatches ($> 48\text{h}$) | Total Shipped Order Lines | $> 4.0\%$ |
| **On-Time Delivery Rate** | Delivered On-Time Lines | Total Delivered Lines | $< 90.0\%$ |
| **Order Defect Rate (ODR)** | Disputed Orders Count | Total Distinct Orders | $> 1.0\%$ |
| **Cancellation Rate (CR)** | Cancelled Order Lines | Total Order Lines | $> 2.5\%$ |
| **Average Rating** | Sum of Review Ratings | Total Customer Reviews | $< 4.2$ |

### 6.1 Time Windows
- `ALL_TIME`: Complete lifetime history.
- `30_DAYS`: Rolling 30 calendar days from reference date.
- `60_DAYS`: Rolling 60 calendar days from reference date.
- `90_DAYS`: Rolling 90 calendar days from reference date.
