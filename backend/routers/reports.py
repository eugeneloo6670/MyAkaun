from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import case, func
from typing import Optional
from database import get_db
from models.entry import Entry
from money import MONEY_TOLERANCE, ZERO, money, money_sum
from datetime import datetime

router = APIRouter()
VISIBLE_BALANCE_TOLERANCE = MONEY_TOLERANCE


def apply_credit(open_purchases: list[dict], amount, linked_to: str | None = None) -> None:
    remaining = money(amount)
    if remaining <= ZERO:
        return

    ordered = open_purchases
    if linked_to:
        linked = [p for p in open_purchases if p["short_id"] == linked_to]
        others = [p for p in open_purchases if p["short_id"] != linked_to]
        ordered = linked + others

    for purchase in ordered:
        if remaining <= ZERO:
            break
        available = purchase["remaining"]
        if available <= ZERO:
            continue
        applied = min(available, remaining)
        purchase["remaining"] = money(available - applied)
        remaining = money(remaining - applied)


def aged_outstanding(entries: list[Entry], now: datetime) -> dict[str, object]:
    purchases = sorted(
        (e for e in entries if e.type == "purchase"),
        key=lambda e: (e.date, e.id or 0),
    )
    open_purchases = [
        {
            "short_id": e.short_id,
            "date": e.date,
            "remaining": money(e.total),
        }
        for e in purchases
    ]

    reductions = sorted(
        (e for e in entries if e.type in {"return", "payment"}),
        key=lambda e: (e.date, e.id or 0),
    )
    for e in reductions:
        if e.type == "return":
            apply_credit(open_purchases, abs(e.total or ZERO), e.linked_to)
        elif e.type == "payment":
            apply_credit(open_purchases, money(e.paid or ZERO) + money(e.discount_received or ZERO))

    aged = {"current": ZERO, "d30": ZERO, "d60": ZERO, "d90plus": ZERO}
    for purchase in open_purchases:
        remaining = purchase["remaining"]
        if remaining <= ZERO:
            continue
        days = (now - datetime.strptime(purchase["date"], "%Y-%m-%d")).days
        if days <= 30:
            aged["current"] = money(aged["current"] + remaining)
        elif days <= 60:
            aged["d30"] = money(aged["d30"] + remaining)
        elif days <= 90:
            aged["d60"] = money(aged["d60"] + remaining)
        else:
            aged["d90plus"] = money(aged["d90plus"] + remaining)
    return aged


@router.get("/month-end/{month}")
def month_end_report(month: str, db: Session = Depends(get_db)):
    # Voided entries must not affect month-end totals.
    entries = db.query(Entry).filter(
        Entry.month == month,
        Entry.status != "voided",
    ).all()
    if not entries:
        return {"month": month, "entries": 0}

    purchases = [e for e in entries if e.type == "purchase"]
    returns   = [e for e in entries if e.type == "return"]
    payments  = [e for e in entries if e.type == "payment"]

    total_purchases = money_sum(e.total for e in purchases)
    total_returns   = money_sum(abs(e.total) for e in returns)
    total_payments  = money_sum(e.paid for e in payments)
    total_discounts = money_sum(e.discount_received for e in payments)
    total_sst       = money_sum(e.sst_amount for e in entries if e.type != "payment")
    net_purchases   = money(total_purchases - total_returns)
    closing_balance = money(total_purchases - total_returns - total_payments - total_discounts)

    gl_groups = {}
    for e in entries:
        if e.type == "payment":
            continue
        key = e.gl_code
        if key not in gl_groups:
            gl_groups[key] = {"code": e.gl_code, "name": e.gl_name, "net": ZERO, "sst": ZERO, "total": ZERO, "count": 0}
        gl_groups[key]["net"]   = money(gl_groups[key]["net"] + e.amount)
        gl_groups[key]["sst"]   = money(gl_groups[key]["sst"] + (e.sst_amount or ZERO))
        gl_groups[key]["total"] = money(gl_groups[key]["total"] + e.total)
        gl_groups[key]["count"] += 1

    missing_docs = len([e for e in entries if not (e.doc_ref or "").strip()])
    missing_refs = len([e for e in entries if not e.reference])

    return {
        "month": month,
        "total_purchases": total_purchases,
        "total_returns": total_returns,
        "net_purchases": net_purchases,
        "total_sst": total_sst,
        "total_payments": total_payments,
        "total_discounts": total_discounts,
        "closing_balance": closing_balance,
        "missing_docs": missing_docs,
        "missing_refs": missing_refs,
        "gl_breakdown": list(gl_groups.values()),
        "entry_count": len(entries),
    }


@router.get("/creditors/count")
def count_creditors(db: Session = Depends(get_db)):
    """Count suppliers with visible non-zero creditor balances.

    The Creditors UI hides fully-settled suppliers, so the sidebar count should
    match that visible table rather than counting every supplier with history.
    """
    balance_expr = (
        func.coalesce(func.sum(case((Entry.type == "purchase", Entry.total), else_=0)), 0)
        - func.coalesce(func.sum(case((Entry.type == "return", func.abs(Entry.total)), else_=0)), 0)
        - func.coalesce(func.sum(case((Entry.type == "payment", func.coalesce(Entry.paid, 0)), else_=0)), 0)
        - func.coalesce(func.sum(case((Entry.type == "payment", func.coalesce(Entry.discount_received, 0)), else_=0)), 0)
    )
    rows = (
        db.query(Entry.supplier)
        .filter(Entry.status != "voided")
        .group_by(Entry.supplier)
        .having(func.abs(balance_expr) > VISIBLE_BALANCE_TOLERANCE)
        .all()
    )
    return {"count": len(rows)}


@router.get("/creditors")
def creditors_report(db: Session = Depends(get_db)):
    # Distinct suppliers from non-voided entries only.
    suppliers = (
        db.query(Entry.supplier)
        .filter(Entry.status != "voided")
        .distinct()
        .all()
    )
    result = []
    now = datetime.utcnow()

    for (supplier,) in suppliers:
        entries = (
            db.query(Entry)
            .filter(Entry.supplier == supplier, Entry.status != "voided")
            .all()
        )
        purchases  = money_sum(e.total for e in entries if e.type == "purchase")
        returns    = money_sum(abs(e.total) for e in entries if e.type == "return")
        payments   = money_sum(e.paid for e in entries if e.type == "payment")
        discounts  = money_sum(e.discount_received for e in entries if e.type == "payment")
        balance    = money(purchases - returns - payments - discounts)
        missing_docs = len([e for e in entries if not (e.doc_ref or "").strip()])

        aged = aged_outstanding(entries, now)

        result.append({
            "supplier": supplier,
            "gross_purchases": purchases,
            "returns": returns,
            "payments": payments,
            "discounts": discounts,
            "balance": balance,
            "aged": aged,
            "missing_docs": missing_docs,
            "transaction_count": len(entries),
        })

    return sorted(result, key=lambda x: abs(x["balance"]), reverse=True)


@router.get("/aged-payables")
def aged_payables(db: Session = Depends(get_db)):
    """Summary of all overdue payables — used by Hermes nightly review."""
    creditors = creditors_report(db)
    overdue = [c for c in creditors if c["aged"]["d60"] > 0 or c["aged"]["d90plus"] > 0]
    return {
        "total_overdue_60d": money_sum(c["aged"]["d60"] for c in overdue),
        "total_overdue_90d": money_sum(c["aged"]["d90plus"] for c in overdue),
        "suppliers": overdue,
    }
