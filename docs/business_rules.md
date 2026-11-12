# Marketplace Business Rules & Financial Policy
**SellerOps Intelligence Platform**

---

## 1. Commission & Fee Calculation Policy

Platform take-rates are governed by product category schedules, adjusted by seller tier volume discounts, with fixed handling charges:

### 1.1 Category Base Rates
- Electronics: 8.0%
- Fashion & Apparel: 15.0%
- Home & Kitchen: 12.0%
- Beauty & Personal Care: 14.0%
- Sports & Outdoors: 10.0%
- Books & Media: 15.0%
- Automotive: 10.0%
- Health & Wellness: 12.5%

### 1.2 Seller Tier Discounts
- **ENTERPRISE** (GMV $\ge \$50,000$): -2.0% discount on category rate.
- **PREFERRED** (GMV $\ge \$10,000$): -1.0% discount on category rate.
- **STANDARD**: Base category rate.
- **PROBATION**: +2.0% risk surcharge.

### 1.3 Fee Formula
$$\text{Effective Rate} = \max(0.01, \text{Base Rate} - \text{Tier Discount})$$
$$\text{Variable Fee} = \max(\text{Gross Amount} \times \text{Effective Rate}, \$0.50)$$
$$\text{Total Commission} = \text{Variable Fee} + \$0.30 \text{ (Fixed Handling Fee)}$$

---

## 2. Risk-Based Rolling Reserve Policy

To protect buyers and the platform against chargeback insolvency, a rolling reserve is withheld from every completed order:

| Seller Tier | Base Reserve Rate | Hold Window | High Risk Surcharge (> 65 Score) |
| :--- | :--- | :--- | :--- |
| **ENTERPRISE** | 5.0% | 7 Days | +5.0% / +7 Days |
| **PREFERRED** | 8.0% | 14 Days | +5.0% / +7 Days |
| **STANDARD** | 10.0% | 14 Days | +5.0% / +7 Days |
| **PROBATION** | 20.0% | 30 Days | +5.0% / +7 Days |
| **SUSPENDED** | 100.0% | 90 Days | Indefinite review |

Reserve maturity timestamp is strictly calculated from the physical delivery timestamp:
$$\text{Release Date} = \text{Delivered Timestamp} + \text{Hold Duration}$$

---

## 3. Payout Eligibility & Disbursement Criteria

An order settlement balance is unlocked for payout batch inclusion **if and only if** all four conditions are satisfied:
1. **Order State:** Must be confirmed `DELIVERED`.
2. **Reserve Maturity:** Current platform time $\ge \text{Release Date}$.
3. **Seller Standing:** Seller status is not `SUSPENDED`.
4. **Dispute Cleared:** No open or pending chargeback investigations.

Minimum payout batch threshold: **\$25.00**.

---

## 4. Fulfillment SLA Guidelines

- **Standard Dispatch Window:** **48 hours** from order creation timestamp.
- **On-Time Criteria:** Dispatch timestamp $-$ Order timestamp $\le 48.0 \text{ hours}$.
- **Late Shipment Violation:** If dispatch exceeds 48 hours, shipment is tagged `LATE`, lowering seller rating and increasing dynamic risk score.
- **Seller Suspension Threshold:**
  - Late Shipment Rate (LSR) $> 4.0\%$
  - Order Defect Rate (ODR) $> 1.0\%$
  - Cancellation Rate (CR) $> 2.5\%$

---

## 5. Dispute Resolution & Financial Clawbacks

- Customer disputes resolved as `RESOLVED_BUYER_FAVOR` or `CHARGEBACK_LOST` mandate immediate financial clawback (`clawback_applied = 1`).
- The refunded principal is clawed back from the seller's next payout batch line items.
- Any failure to claw back funds creates an operational leak (**Anomaly 4**).
