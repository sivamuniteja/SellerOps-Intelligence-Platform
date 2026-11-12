"""Deterministic Payout, Ledgers & Banking Event Generator with Anomalies 1, 2, and 5."""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from src.config import PlatformConfig


def generate_settlements_and_payouts(
    order_lines: List[Dict[str, Any]],
    orders: List[Dict[str, Any]],
    sellers: List[Dict[str, Any]],
    listings: List[Dict[str, Any]],
    fulfillments: List[Dict[str, Any]],
    disputes: List[Dict[str, Any]],
    commission_rules: List[Dict[str, Any]],
    config: PlatformConfig,
    seed: int = 20261022,
    anomaly_1_count: int = 25,
    anomaly_2_count: int = 25,
    anomaly_5_count: int = 20,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate double-entry ledgers, payout batches, payout lines, and immutable payout events.
    All calculations use exact integer cents.
    Injects:
      - Anomaly 1: Premature payout line disbursed prior to delivery or hold release.
      - Anomaly 2: Duplicate commission fee charged in commission ledger.
      - Anomaly 5: Batch header net does not equal sum of payout lines.
    Returns (commission_ledger, reserve_ledger, payouts, payout_lines, payout_events, ground_truth_anomalies).
    """
    rng = random.Random(seed)
    seller_map = {s["seller_id"]: s for s in sellers}
    listing_map = {l["listing_id"]: l for l in listings}
    order_map = {o["order_id"]: o for o in orders}
    flf_map = {f["order_line_id"]: f for f in fulfillments}

    # Map commission rules by (category, tier)
    rule_lookup = {(r["category"], r["seller_tier"]): r for r in commission_rules}

    commission_ledger = []
    reserve_ledger = []
    payouts = []
    payout_lines = []
    payout_events = []
    ground_truth = []

    simulated_now = datetime(2026, 11, 10, 0, 0, 0)
    ano_2_injected = 0
    cml_idx = 1
    rsv_idx = 1

    # 1. Build Commission & Reserve Ledgers
    for line in order_lines:
        line_id = line["order_line_id"]
        seller = seller_map[line["seller_id"]]
        listing = listing_map[line["listing_id"]]
        order = order_map[line["order_id"]]
        gross_cents = line["gross_amount_cents"]
        category = listing["category"]
        tier = seller["tier"]

        # Commission Calculation
        rule = rule_lookup.get((category, tier))
        base_bps = rule["base_rate_basis_points"] if rule else 800
        min_cents = rule["min_commission_cents"] if rule else 50
        fixed_cents = rule["fixed_fee_cents"] if rule else 30

        raw_variable = (gross_cents * base_bps) // 10000
        variable_fee = max(raw_variable, min_cents)
        total_comm_cents = variable_fee + fixed_cents

        # Anomaly 2: Double commission
        if ano_2_injected < anomaly_2_count and line["line_status"] == "DELIVERED":
            total_comm_cents = total_comm_cents * 2
            ano_2_injected += 1
            ground_truth.append({
                "anomaly_id": f"ANO-2-{ano_2_injected:04d}",
                "anomaly_type": "DOUBLE_COMMISSION",
                "entity_type": "SETTLEMENT",
                "entity_id": f"CML-{cml_idx:06d}",
                "description": f"Commission entry CML-{cml_idx:06d} for line {line_id} charged double fee ({total_comm_cents} cents)",
                "severity": "HIGH",
                "detected": 0,
                "created_at": order["order_date"],
            })

        commission_ledger.append({
            "entry_id": f"CML-{cml_idx:06d}",
            "order_line_id": line_id,
            "seller_id": seller["seller_id"],
            "rule_id": rule["rule_id"] if rule else None,
            "gross_amount_cents": gross_cents,
            "rate_basis_points": base_bps,
            "variable_fee_cents": variable_fee,
            "fixed_fee_cents": fixed_cents,
            "total_commission_cents": total_comm_cents,
            "created_at": order["order_date"],
        })
        cml_idx += 1

        # Reserve Calculation
        tier_cfg = config.seller_tiers.get(tier)
        base_res_rate = tier_cfg.reserve_rate if tier_cfg else 0.10
        hold_days = tier_cfg.hold_days if tier_cfg else 14
        if seller["risk_score"] > 65.0:
            base_res_rate += 0.05
            hold_days += 7

        res_bps = int(min(1.0, base_res_rate) * 10000)
        res_cents = (gross_cents * res_bps) // 10000

        flf = flf_map.get(line_id)
        deliv_str = flf.get("delivered_at") if flf and flf.get("delivered_at") else order["order_date"]
        deliv_dt = datetime.strptime(deliv_str, "%Y-%m-%d %H:%M:%S")
        release_dt = deliv_dt + timedelta(days=hold_days)
        release_str = release_dt.strftime("%Y-%m-%d %H:%M:%S")

        is_delivered = line["line_status"] == "DELIVERED"
        is_matured = simulated_now >= release_dt
        reserve_status = "RELEASED" if (is_delivered and is_matured and seller["status"] != "SUSPENDED") else "HELD"

        reserve_ledger.append({
            "entry_id": f"RSV-{rsv_idx:06d}",
            "order_line_id": line_id,
            "seller_id": seller["seller_id"],
            "reserve_rate_basis_points": res_bps,
            "reserve_amount_cents": res_cents,
            "hold_days": hold_days,
            "release_scheduled_date": release_str,
            "status": reserve_status,
            "released_at": release_str if reserve_status == "RELEASED" else None,
            "created_at": order["order_date"],
        })
        rsv_idx += 1

    # Map ledgers by order_line_id
    comm_map = {c["order_line_id"]: c for c in commission_ledger}
    res_map = {r["order_line_id"]: r for r in reserve_ledger}

    # Group eligible lines by seller
    eligible_lines_by_seller: Dict[str, List[Dict[str, Any]]] = {}
    unmatured_lines: List[Dict[str, Any]] = []

    for line in order_lines:
        line_id = line["order_line_id"]
        res_entry = res_map.get(line_id)
        seller = seller_map[line["seller_id"]]

        is_eligible = (
            line["line_status"] == "DELIVERED"
            and res_entry
            and res_entry["status"] == "RELEASED"
            and seller["status"] != "SUSPENDED"
        )

        if is_eligible:
            sid = line["seller_id"]
            if sid not in eligible_lines_by_seller:
                eligible_lines_by_seller[sid] = []
            eligible_lines_by_seller[sid].append(line)
        else:
            if line["gross_amount_cents"] > 5000:
                unmatured_lines.append(line)

    # 2. Build Payout Batches
    payout_idx = 1
    event_idx = 1
    ano_5_injected = 0
    ano_1_injected = 0

    for seller_id, lines in eligible_lines_by_seller.items():
        if len(lines) < 2:
            continue

        seller = seller_map[seller_id]
        po_id = f"PAYOUT-2026-{payout_idx:06d}"

        # batch_date >= max release_scheduled_date
        max_rel_dt = max(
            datetime.strptime(res_map[l["order_line_id"]]["release_scheduled_date"], "%Y-%m-%d %H:%M:%S")
            for l in lines[:25]
        )
        batch_date = max_rel_dt + timedelta(days=1)
        batch_str = batch_date.strftime("%Y-%m-%d %H:%M:%S")

        should_mismatch = (ano_5_injected < anomaly_5_count)
        if should_mismatch:
            ano_5_injected += 1

        batch_gross = 0
        batch_comm = 0
        batch_res = 0
        batch_net = 0
        current_batch_lines = []

        for line_pos, line in enumerate(lines[:25]):
            lid = line["order_line_id"]
            c_entry = comm_map[lid]
            r_entry = res_map[lid]

            g = line["gross_amount_cents"]
            c = c_entry["total_commission_cents"]
            r = r_entry["reserve_amount_cents"]
            net_line = g - c - r

            batch_gross += g
            batch_comm += c
            batch_res += r
            batch_net += net_line

            line_entry_id = f"PLN-{po_id}-{line_pos+1:02d}"
            current_batch_lines.append({
                "line_id": line_entry_id,
                "payout_id": po_id,
                "order_line_id": lid,
                "gross_amount_cents": g,
                "commission_deducted_cents": c,
                "reserve_deducted_cents": r,
                "dispute_deducted_cents": 0,
                "net_line_amount_cents": net_line,
                "created_at": batch_str,
            })

        final_net = batch_net
        recon_status = "MATCHED"

        if should_mismatch:
            final_net = batch_net + 12500  # Artificially alter by +$125.00
            recon_status = "DISCREPANCY"
            ground_truth.append({
                "anomaly_id": f"ANO-5-{ano_5_injected:04d}",
                "anomaly_type": "PAYOUT_TOTAL_MISMATCH",
                "entity_type": "PAYOUT",
                "entity_id": po_id,
                "description": f"Payout batch {po_id} header net altered by +12500 cents ($125.00) vs lines sum",
                "severity": "CRITICAL",
                "detected": 0,
                "created_at": batch_str,
            })

        payout_status = "PAID"
        if seller["status"] == "SUSPENDED" or final_net < 2500:
            payout_status = "HELD"

        payouts.append({
            "payout_id": po_id,
            "seller_id": seller_id,
            "batch_date": batch_str,
            "total_lines_count": len(current_batch_lines),
            "gross_sales_cents": batch_gross,
            "total_commission_cents": batch_comm,
            "total_reserve_held_cents": batch_res,
            "total_disputes_deducted_cents": 0,
            "net_payout_amount_cents": final_net,
            "payout_status": payout_status,
            "reconciliation_status": recon_status,
            "created_at": batch_str,
        })
        payout_lines.extend(current_batch_lines)

        # Immutable Payout Events: PROCESSING -> PAID / HELD
        payout_events.append({
            "event_id": f"POE-{event_idx:06d}",
            "payout_id": po_id,
            "previous_status": "SCHEDULED",
            "new_status": "PROCESSING",
            "gateway_reference": f"ACH-INIT-{payout_idx:06d}",
            "notes": "Banking file queued for NACHA transfer",
            "created_at": batch_str,
        })
        event_idx += 1

        payout_events.append({
            "event_id": f"POE-{event_idx:06d}",
            "payout_id": po_id,
            "previous_status": "PROCESSING",
            "new_status": payout_status,
            "gateway_reference": f"ACH-CONF-{payout_idx:06d}",
            "notes": "ACH direct deposit settled successfully" if payout_status == "PAID" else "Disbursement held pending risk review",
            "created_at": batch_str,
        })
        event_idx += 1
        payout_idx += 1

    # 3. Anomaly 1: Premature Payouts (exactly 25)
    sampled_premature = rng.sample(unmatured_lines, min(anomaly_1_count, len(unmatured_lines)))
    for unmat in sampled_premature:
        ano_1_injected += 1
        po_id = f"PAYOUT-PREM-{ano_1_injected:04d}"
        line_entry_id = f"PLN-{po_id}-01"
        seller = seller_map[unmat["seller_id"]]

        r_entry = res_map[unmat["order_line_id"]]
        rel_dt = datetime.strptime(r_entry["release_scheduled_date"], "%Y-%m-%d %H:%M:%S")
        premature_dt = rel_dt - timedelta(days=10)
        premature_str = premature_dt.strftime("%Y-%m-%d %H:%M:%S")

        c_entry = comm_map[unmat["order_line_id"]]
        g = unmat["gross_amount_cents"]
        c = c_entry["total_commission_cents"]
        r = r_entry["reserve_amount_cents"]
        net_premature = g - c - r

        payout_lines.append({
            "line_id": line_entry_id,
            "payout_id": po_id,
            "order_line_id": unmat["order_line_id"],
            "gross_amount_cents": g,
            "commission_deducted_cents": c,
            "reserve_deducted_cents": r,
            "dispute_deducted_cents": 0,
            "net_line_amount_cents": net_premature,
            "created_at": premature_str,
        })

        payouts.append({
            "payout_id": po_id,
            "seller_id": seller["seller_id"],
            "batch_date": premature_str,
            "total_lines_count": 1,
            "gross_sales_cents": g,
            "total_commission_cents": c,
            "total_reserve_held_cents": r,
            "total_disputes_deducted_cents": 0,
            "net_payout_amount_cents": net_premature,
            "payout_status": "PAID",
            "reconciliation_status": "MATCHED",
            "created_at": premature_str,
        })

        ground_truth.append({
            "anomaly_id": f"ANO-1-{ano_1_injected:04d}",
            "anomaly_type": "PREMATURE_PAYOUT",
            "entity_type": "PAYOUT_LINE",
            "entity_id": line_entry_id,
            "description": f"Payout line {line_entry_id} disbursed order line {unmat['order_line_id']} 10 days before reserve maturity",
            "severity": "CRITICAL",
            "detected": 0,
            "created_at": premature_str,
        })

    return commission_ledger, reserve_ledger, payouts, payout_lines, payout_events, ground_truth
