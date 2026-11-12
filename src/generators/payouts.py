"""Deterministic Payout & Settlement Generator with Isolated Anomalies 1, 2, and 5."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from src.config import PlatformConfig
from src.services.commission_engine import CommissionEngine
from src.services.reserve_engine import ReserveEngine
from src.services.payout_engine import PayoutEngine


def generate_settlements_and_payouts(
    orders: List[Dict[str, Any]],
    sellers: List[Dict[str, Any]],
    listings: List[Dict[str, Any]],
    fulfillments: List[Dict[str, Any]],
    disputes: List[Dict[str, Any]],
    config: PlatformConfig,
    seed: int = 42,
    anomaly_1_count: int = 25,
    anomaly_2_count: int = 25,
    anomaly_5_count: int = 20,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate order settlements, payout batches, and line items.
    Injects:
      - Anomaly 1: Premature payout before delivery or hold release (exactly 25).
      - Anomaly 2: Commission applied twice on settlement (exactly 25).
      - Anomaly 5: Payout batch total does not equal sum of payout lines (exactly 20).
    Returns (settlements, payout_batches, payout_lines, ground_truth_anomalies).
    """
    rng = random.Random(seed)
    comm_engine = CommissionEngine(config)
    reserve_engine = ReserveEngine(config)
    payout_engine = PayoutEngine(config)

    seller_lookup = {s["seller_id"]: s for s in sellers}
    listing_lookup = {l["listing_id"]: l for l in listings}
    flf_lookup = {f["order_id"]: f for f in fulfillments}

    ground_truth = []
    settlements = []

    # 1. Generate Order Settlements
    ano_2_injected = 0
    simulated_now = datetime(2026, 11, 10, 0, 0, 0)

    for idx, order in enumerate(orders):
        settlement_id = f"STL-{idx+1:06d}"
        seller = seller_lookup[order["seller_id"]]
        listing = listing_lookup[order["listing_id"]]
        gross = order["gross_amount"]
        seller_tier = seller["tier"]
        category = listing["category"]

        order_dt = datetime.strptime(order["order_date"], "%Y-%m-%d %H:%M:%S")
        flf = flf_lookup.get(order["order_id"])

        deliv_str = flf.get("delivered_at") if flf else None
        deliv_dt = datetime.strptime(deliv_str, "%Y-%m-%d %H:%M:%S") if deliv_str else (order_dt + timedelta(days=5))

        # Commission
        comm_calc = comm_engine.calculate_commission(gross, category, seller_tier)
        comm_rate = comm_calc["effective_rate"]
        comm_amt = comm_calc["total_commission"]

        # Anomaly 2: Double commission
        if ano_2_injected < anomaly_2_count and order["order_status"] == "DELIVERED":
            comm_amt = round(comm_amt * 2.0, 2)
            ano_2_injected += 1
            ground_truth.append({
                "anomaly_id": f"ANO-2-{ano_2_injected:04d}",
                "anomaly_type": "DOUBLE_COMMISSION",
                "entity_type": "SETTLEMENT",
                "entity_id": settlement_id,
                "description": f"Settlement {settlement_id} for order {order['order_id']} charged duplicate commission (${comm_amt})",
                "severity": "HIGH",
                "detected": 0,
                "created_at": order_dt.strftime("%Y-%m-%d %H:%M:%S"),
            })

        # Reserve
        res_calc = reserve_engine.calculate_reserve(gross, seller_tier, seller["risk_score"], deliv_dt)
        res_rate = res_calc["reserve_rate"]
        res_amt = res_calc["reserve_amount"]
        release_dt = res_calc["release_date"]

        # Net seller amount
        net_amt = round(gross - comm_amt - res_amt, 2)

        is_delivered = order["order_status"] == "DELIVERED"
        reserve_matured = simulated_now >= release_dt
        reserve_released = 1 if (is_delivered and reserve_matured and seller["status"] != "SUSPENDED") else 0
        is_eligible = 1 if (is_delivered and reserve_released and seller["status"] != "SUSPENDED") else 0

        settlements.append({
            "settlement_id": settlement_id,
            "order_id": order["order_id"],
            "seller_id": order["seller_id"],
            "gross_amount": gross,
            "commission_rate": comm_rate,
            "commission_amount": comm_amt,
            "reserve_rate": res_rate,
            "reserve_amount": res_amt,
            "reserve_release_date": release_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "reserve_released": reserve_released,
            "net_seller_amount": net_amt,
            "is_eligible_for_payout": is_eligible,
            "created_at": order_dt.strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Group eligible orders by seller for payout generation
    eligible_orders_by_seller: Dict[str, List[Dict[str, Any]]] = {}
    for s in settlements:
        if s["is_eligible_for_payout"] == 1:
            sid = s["seller_id"]
            if sid not in eligible_orders_by_seller:
                eligible_orders_by_seller[sid] = []
            eligible_orders_by_seller[sid].append(s)

    payout_batches = []
    payout_lines = []
    payout_idx = 1
    ano_5_injected = 0
    ano_1_injected = 0

    # 2. Build normal payout batches
    for seller_id, items in eligible_orders_by_seller.items():
        if len(items) < 3:
            continue

        seller = seller_lookup[seller_id]
        po_id = f"PO-{payout_idx:06d}"

        # batch_date must be >= max reserve_release_date in this batch
        max_release_dt = max(
            datetime.strptime(it["reserve_release_date"], "%Y-%m-%d %H:%M:%S")
            for it in items[:30]
        )
        batch_date = max_release_dt + timedelta(days=1)

        should_mismatch = (ano_5_injected < anomaly_5_count)
        if should_mismatch:
            ano_5_injected += 1

        batch_result = payout_engine.build_payout_batch(
            payout_id=po_id,
            seller_id=seller_id,
            batch_date=batch_date,
            eligible_items=items[:30],
            seller_status=seller["status"],
            inject_mismatch=should_mismatch,
        )

        if batch_result:
            payout_batches.append(batch_result["header"])
            payout_lines.extend(batch_result["lines"])

            if should_mismatch:
                ground_truth.append({
                    "anomaly_id": f"ANO-5-{ano_5_injected:04d}",
                    "anomaly_type": "PAYOUT_TOTAL_MISMATCH",
                    "entity_type": "PAYOUT",
                    "entity_id": po_id,
                    "description": f"Payout batch {po_id} header net mismatch of $125.00 vs lines sum",
                    "severity": "CRITICAL",
                    "detected": 0,
                    "created_at": order_dt.strftime("%Y-%m-%d %H:%M:%S"),
                })

            payout_idx += 1

    # 3. Anomaly 1: Premature Payout injection (exactly 25)
    # Create isolated batches for premature orders where batch_date < release_date or order not delivered
    unmatured_settlements = [
        s for s in settlements
        if s["is_eligible_for_payout"] == 0 and s["gross_amount"] > 50.0
    ]
    sampled_premature = rng.sample(unmatured_settlements, min(anomaly_1_count, len(unmatured_settlements)))

    for unmat in sampled_premature:
        ano_1_injected += 1
        po_id = f"PO-PREM-{ano_1_injected:04d}"
        line_id = f"LN-ANO1-{ano_1_injected:04d}"
        seller = seller_lookup[unmat["seller_id"]]

        # Batch date is intentionally set 10 days BEFORE reserve maturity
        rel_dt = datetime.strptime(unmat["reserve_release_date"], "%Y-%m-%d %H:%M:%S")
        premature_batch_dt = rel_dt - timedelta(days=10)

        gross = unmat["gross_amount"]
        comm = unmat["commission_amount"]
        res = unmat["reserve_amount"]
        net = unmat["net_seller_amount"]

        # Line item
        payout_lines.append({
            "line_id": line_id,
            "payout_id": po_id,
            "order_id": unmat["order_id"],
            "order_amount": gross,
            "commission_deducted": comm,
            "reserve_deducted": res,
            "dispute_deducted": 0.0,
            "net_line_amount": net,
            "created_at": premature_batch_dt.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # Matching header so it does NOT trigger Anomaly 5
        payout_batches.append({
            "payout_id": po_id,
            "seller_id": seller["seller_id"],
            "batch_date": premature_batch_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "total_orders_count": 1,
            "gross_sales": gross,
            "total_commission": comm,
            "total_reserve_held": res,
            "total_disputes_deducted": 0.0,
            "net_payout_amount": net,
            "payout_status": "PAID",
            "reconciliation_status": "MATCHED",
            "created_at": premature_batch_dt.strftime("%Y-%m-%d %H:%M:%S"),
        })

        ground_truth.append({
            "anomaly_id": f"ANO-1-{ano_1_injected:04d}",
            "anomaly_type": "PREMATURE_PAYOUT",
            "entity_type": "PAYOUT_LINE",
            "entity_id": line_id,
            "description": f"Payout line {line_id} disbursed order {unmat['order_id']} prior to delivery or reserve maturity ({unmat['reserve_release_date']})",
            "severity": "CRITICAL",
            "detected": 0,
            "created_at": premature_batch_dt.strftime("%Y-%m-%d %H:%M:%S"),
        })

    return settlements, payout_batches, payout_lines, ground_truth
