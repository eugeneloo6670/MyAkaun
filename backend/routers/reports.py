from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from database import get_db
from models.entry import Entry
from datetime import datetime

router = APIRouter()


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

    total_purchases = round(sum(e.total for e in purchases), 2)
    total_returns   = round(sum(abs(e.total) for e in returns), 2)
    total_payments  = round(sum(e.paid or 0 for e in payments), 2)
    total_discounts = round(sum(e.discount_received or 0 for e in payments), 2)
    total_sst       = round(sum(e.sst_amount or 0 for e in entries if e.type != "payment"), 2)
    net_purchases   = round(total_purchases - total_returns, 2)
    closing_balance = round(total_purchases - total_returns - total_payments - total_discounts, 2)

    gl_groups = {}
    for e in entries:
        if e.type == "payment":
            continue
        key = e.gl_code
        if key not in gl_groups:
            gl_groups[key] = {"code": e.gl_code, "name": e.gl_name, "net": 0, "sst": 0, "total": 0, "count": 0}
        gl_groups[key]["net"]   = round(gl_groups[key]["net"] + e.amount, 2)
        gl_groups[key]["sst"]   = round(gl_groups[key]["sst"] + (e.sst_amount or 0), 2)
        gl_groups[key]["total"] = round(gl_groups[key]["total"] + e.total, 2)
        gl_groups[key]["count"] += 1

    missing_docs = len([e for e in entries if not e.doc_ref])
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
    """Count of distinct suppliers with non-voided entries.

    Mirrors the row count of /api/reports/creditors without running the full
    aggregation. Used by Sidebar badges.
    """
    count = (
        db.query(func.count(func.distinct(Entry.supplier)))
        .filter(Entry.status != "voided")
        .scalar()
        or 0
    )
    return {"count": count}


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
        purchases  = round(sum(e.total for e in entries if e.type == "purchase"), 2)
        returns    = round(sum(abs(e.total) for e in entries if e.type == "return"), 2)
        payments   = round(sum(e.paid or 0 for e in entries if e.type == "payment"), 2)
        discounts  = round(sum(e.discount_received or 0 for e in entries if e.type == "payment"), 2)
        balance    = round(purchases - returns - payments - discounts, 2)
        missing_docs = len([e for e in entries if not e.doc_ref])

        # Aged payables buckets
        aged = {"current": 0, "d30": 0, "d60": 0, "d90plus": 0}
        for e in entries:
            if e.type != "purchase":
                continue
            days = (now - datetime.strptime(e.date, "%Y-%m-%d")).days
            if days <= 30:
                aged["current"] = round(aged["current"] + e.total, 2)
            elif days <= 60:
                aged["d30"] = round(aged["d30"] + e.total, 2)
            elif days <= 90:
                aged["d60"] = round(aged["d60"] + e.total, 2)
            else:
                aged["d90plus"] = round(aged["d90plus"] + e.total, 2)

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
        "total_overdue_60d": round(sum(c["aged"]["d60"] for c in overdue), 2),
        "total_overdue_90d": round(sum(c["aged"]["d90plus"] for c in overdue), 2),
        "suppliers": overdue,
    }
