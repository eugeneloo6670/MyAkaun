from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel
import hashlib
import json
from database import get_db
from models.entry import Entry, AuditLog, SupplierMemory

router = APIRouter()

EntryType = Literal["purchase", "return", "payment"]
MONEY_TOLERANCE = 0.005

class EntryCreate(BaseModel):
    date: str
    type: EntryType
    supplier: str
    reference: Optional[str] = None
    description: Optional[str] = None
    gl_code: Optional[str] = None
    gl_name: Optional[str] = None
    amount: float
    sst_rate: float = 0
    sst_amount: float = 0
    total: float
    orig_ccy: str = "MYR"
    orig_amount: Optional[float] = None
    fx_rate: Optional[float] = None
    doc_ref: Optional[str] = None
    linked_to: Optional[str] = None
    recorded_by: Optional[str] = "System"
    # Payment fields
    paid: Optional[float] = None
    balance_owed: Optional[float] = None
    discount_received: Optional[float] = None


def missing_doc_clause():
    return or_(Entry.doc_ref == None, func.trim(Entry.doc_ref) == "")


def supplier_balance(entries) -> float:
    purchases = sum(e.total or 0 for e in entries if e.type == "purchase")
    returns = sum(abs(e.total or 0) for e in entries if e.type == "return")
    payments = sum(e.paid or 0 for e in entries if e.type == "payment")
    discounts = sum(e.discount_received or 0 for e in entries if e.type == "payment")
    return round(purchases - returns - payments - discounts, 2)


def payload_fingerprint(payload: EntryCreate) -> str:
    raw = payload.model_dump(mode="json")
    encoded = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_entry_invariants(payload: EntryCreate, db: Session) -> None:
    """Server-side invariants. Frontend enforces some of these for UX, but the
    backend re-checks so that direct API/MCP callers cannot bypass.

    Raises HTTPException(400) on the first violated rule.
    """
    # 1. Date is well-formed (YYYY-MM-DD).
    try:
        datetime.strptime(payload.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    # 2. Supplier non-empty.
    if not payload.supplier or not payload.supplier.strip():
        raise HTTPException(status_code=400, detail="supplier is required")

    # 3. Type-specific rules.
    if payload.type == "purchase":
        if payload.total <= 0:
            raise HTTPException(status_code=400, detail="purchase total must be positive")
        if not payload.gl_code:
            raise HTTPException(status_code=400, detail="purchase requires a GL code")
        if payload.linked_to:
            raise HTTPException(status_code=400, detail="purchase cannot have linked_to")

    elif payload.type == "return":
        if payload.total >= 0:
            raise HTTPException(status_code=400, detail="return total must be negative")
        if not payload.linked_to:
            raise HTTPException(status_code=400, detail="return must specify linked_to (original purchase short_id)")
        # Linked entry must exist, be a purchase, and belong to the same supplier.
        linked = db.query(Entry).filter_by(short_id=payload.linked_to).first()
        if not linked:
            raise HTTPException(status_code=400, detail=f"linked_to {payload.linked_to} not found")
        if linked.type != "purchase":
            raise HTTPException(status_code=400, detail="linked_to must reference a purchase")
        if linked.supplier != payload.supplier:
            raise HTTPException(status_code=400, detail="linked_to supplier does not match this entry")
        if linked.status == "voided":
            raise HTTPException(status_code=400, detail="cannot link to a voided entry")
        existing_returns = (
            db.query(Entry)
            .filter(
                Entry.type == "return",
                Entry.linked_to == linked.short_id,
                Entry.status != "voided",
            )
            .all()
        )
        returned_total = sum(abs(e.total or 0) for e in existing_returns)
        if returned_total + abs(payload.total) > (linked.total or 0) + MONEY_TOLERANCE:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"return total exceeds original purchase balance for {linked.short_id}. "
                    f"Already returned {returned_total:.2f}; purchase total is {(linked.total or 0):.2f}."
                ),
            )

    elif payload.type == "payment":
        if payload.paid is None or payload.paid <= 0:
            raise HTTPException(status_code=400, detail="payment requires paid > 0")
        if payload.balance_owed is None:
            raise HTTPException(status_code=400, detail="payment requires balance_owed (use 0 explicitly if there is no outstanding balance)")
        if payload.discount_received is not None:
            if payload.discount_received < 0:
                raise HTTPException(status_code=400, detail="discount_received cannot be negative")
            if payload.discount_received > payload.balance_owed:
                raise HTTPException(status_code=400, detail="discount_received cannot exceed balance_owed")
            # paid + discount must not exceed balance unless explicit overpayment
            if payload.paid + payload.discount_received > payload.balance_owed + MONEY_TOLERANCE:
                raise HTTPException(
                    status_code=400,
                    detail="paid + discount_received exceeds balance_owed (overpayment must be handled explicitly)",
                )
        else:
            # No discount supplied: paid must not exceed balance. Overpayments are
            # not currently modeled — if a real overpayment scenario surfaces
            # (supplier refund, credit balance), that needs its own design.
            # Reject here rather than silently accept and produce a negative
            # creditor balance.
            if payload.paid > payload.balance_owed + MONEY_TOLERANCE:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "paid exceeds balance_owed and no discount was specified. "
                        "If the supplier accepted less than full balance and the "
                        "difference is a settlement discount, set discount_received. "
                        "Overpayments are not currently supported."
                    ),
                )

    # 4. SST sanity (gross >= net).
    if payload.sst_amount and abs(payload.sst_amount) > abs(payload.total):
        raise HTTPException(status_code=400, detail="sst_amount cannot exceed total")


def get_month(date_str: str) -> str:
    return date_str[:7]  # YYYY-MM


def log_action(db: Session, action: str, entry: Entry, user: str, desc: str = None):
    log = AuditLog(
        action=action,
        entry_id=entry.id,
        short_id=entry.short_id,
        user_name=user,
        supplier=entry.supplier,
        reference=entry.reference,
        entry_type=entry.type,
        amount=entry.total,
        doc_ref=entry.doc_ref,
        description=desc
    )
    db.add(log)


def update_supplier_memory(db: Session, entry: Entry):
    mem = db.query(SupplierMemory).filter_by(supplier=entry.supplier).first()
    if not mem:
        mem = SupplierMemory(supplier=entry.supplier)
        db.add(mem)
    mem.entry_count = (mem.entry_count or 0) + 1
    mem.last_seen = datetime.utcnow()
    if entry.gl_code and entry.gl_code != "2100":
        mem.last_gl = f"{entry.gl_code}|{entry.gl_name}"
    if entry.orig_ccy:
        mem.last_ccy = entry.orig_ccy


@router.post("/")
def create_entry(
    payload: EntryCreate,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    key = idempotency_key.strip() if idempotency_key else None
    if key and len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key must be 128 characters or fewer")

    fingerprint = payload_fingerprint(payload) if key else None
    if key:
        existing = db.query(Entry).filter_by(idempotency_key=key).first()
        if existing:
            if existing.idempotency_hash != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key was already used for a different entry payload",
                )
            return existing

    from models.entry import Period
    month = get_month(payload.date)
    period = db.query(Period).filter_by(month=month).first()
    if period and period.locked:
        raise HTTPException(status_code=400, detail=f"Period {month} is locked.")

    # Server-side invariants (type/sign/linkage/payment-balance).
    validate_entry_invariants(payload, db)

    entry = Entry(
        date=payload.date,
        month=month,
        type=payload.type,
        supplier=payload.supplier,
        reference=payload.reference,
        description=payload.description,
        gl_code=payload.gl_code,
        gl_name=payload.gl_name,
        amount=payload.amount,
        sst_rate=payload.sst_rate,
        sst_amount=payload.sst_amount,
        total=payload.total,
        orig_ccy=payload.orig_ccy,
        orig_amount=payload.orig_amount,
        fx_rate=payload.fx_rate,
        doc_ref=payload.doc_ref,
        linked_to=payload.linked_to,
        idempotency_key=key,
        idempotency_hash=fingerprint,
        recorded_by=payload.recorded_by,
        paid=payload.paid,
        balance_owed=payload.balance_owed,
        discount_received=payload.discount_received,
    )
    db.add(entry)
    db.flush()
    log_action(db, "CREATE", entry, payload.recorded_by or "System",
               f"Entry created: {payload.description or ''}")
    update_supplier_memory(db, entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if key:
            existing = db.query(Entry).filter_by(idempotency_key=key).first()
            if existing and existing.idempotency_hash == fingerprint:
                return existing
        raise
    db.refresh(entry)
    return entry


@router.get("/")
def list_entries(
    month: Optional[str] = None,
    supplier: Optional[str] = None,
    type: Optional[str] = None,
    missing_docs: Optional[bool] = None,
    linked_to: Optional[str] = None,
    status: Optional[str] = None,
    include_voided: bool = False,
    db: Session = Depends(get_db)
):
    q = db.query(Entry)
    if month:
        q = q.filter(Entry.month == month)
    if supplier:
        q = q.filter(Entry.supplier == supplier)
    if type:
        q = q.filter(Entry.type == type)
    if missing_docs:
        q = q.filter(missing_doc_clause())
    if linked_to:
        q = q.filter(Entry.linked_to == linked_to)
    if status:
        q = q.filter(Entry.status == status)
    elif not include_voided:
        # Default: hide voided entries from the ledger view.
        q = q.filter(Entry.status != "voided")
    return q.order_by(Entry.date.desc()).all()


@router.get("/count")
def count_entries(
    month: Optional[str] = None,
    supplier: Optional[str] = None,
    type: Optional[str] = None,
    missing_docs: Optional[bool] = None,
    linked_to: Optional[str] = None,
    status: Optional[str] = None,
    include_voided: bool = False,
    db: Session = Depends(get_db)
):
    """Return the row count matching the same filters as list_entries.

    Cheap database COUNT(*) instead of returning a full list and counting in
    the frontend. Used by Sidebar badges.
    """
    q = db.query(func.count(Entry.id))
    if month:
        q = q.filter(Entry.month == month)
    if supplier:
        q = q.filter(Entry.supplier == supplier)
    if type:
        q = q.filter(Entry.type == type)
    if missing_docs:
        q = q.filter(missing_doc_clause())
    if linked_to:
        q = q.filter(Entry.linked_to == linked_to)
    if status:
        q = q.filter(Entry.status == status)
    elif not include_voided:
        q = q.filter(Entry.status != "voided")
    return {"count": q.scalar() or 0}


@router.get("/missing-docs/count")
def count_missing_docs(db: Session = Depends(get_db)):
    """Convenience endpoint for the Sidebar red badge. Counts non-voided
    entries missing a doc_ref.
    """
    count = (
        db.query(func.count(Entry.id))
        .filter(missing_doc_clause(), Entry.status != "voided")
        .scalar()
        or 0
    )
    return {"count": count}


@router.get("/{entry_id}")
def get_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


class VoidRequest(BaseModel):
    voided_by: str
    reason: Optional[str] = None


@router.post("/{entry_id}/void")
def void_entry(entry_id: int, payload: VoidRequest, db: Session = Depends(get_db)):
    """Mark an entry as voided. The row is NEVER deleted. All reports and the
    creditors view filter out voided rows. The audit log records the void.

    Voiding a parent purchase that still has non-voided returns/credit notes
    linked to it would corrupt creditor balances (the parent disappears from
    reports but the children remain). We therefore reject voids on entries that
    have non-voided children, and the user must void the children first.

    Payments are supplier-level rather than purchase-level, so they are guarded
    separately: voiding a purchase is rejected if active payments would leave
    that supplier with a negative balance.

    To restore an entry, an admin-only un-void path would be needed; intentionally
    not exposed here.
    """
    entry = db.query(Entry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if entry.status == "voided":
        raise HTTPException(status_code=400, detail="Entry is already voided")

    from models.entry import Period
    period = db.query(Period).filter_by(month=entry.month).first()
    if period and period.locked:
        raise HTTPException(status_code=400, detail=f"Period {entry.month} is locked.")

    # Reject if any non-voided child entries link to this one. Voiding a parent
    # while leaving its returns/credit notes active would break creditor balances.
    children = (
        db.query(Entry)
        .filter(Entry.linked_to == entry.short_id, Entry.status != "voided")
        .all()
    )
    if children:
        child_ids = ", ".join(c.short_id for c in children)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot void {entry.short_id}: it has {len(children)} linked "
                f"non-voided entr{'y' if len(children) == 1 else 'ies'} ({child_ids}). "
                f"Void the linked entr{'y' if len(children) == 1 else 'ies'} first."
            ),
        )

    if entry.type == "purchase":
        active_supplier_entries = (
            db.query(Entry)
            .filter(
                Entry.supplier == entry.supplier,
                Entry.status != "voided",
                Entry.id != entry.id,
            )
            .all()
        )
        active_payments = [e for e in active_supplier_entries if e.type == "payment"]
        balance_after_void = supplier_balance(active_supplier_entries)
        if active_payments and balance_after_void < -MONEY_TOLERANCE:
            payment_ids = ", ".join(e.short_id for e in active_payments)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot void {entry.short_id}: supplier has active payment"
                    f"{'s' if len(active_payments) != 1 else ''} ({payment_ids}) and "
                    f"voiding this purchase would leave a negative balance of "
                    f"{balance_after_void:.2f}. Void or reverse the payment first."
                ),
            )

    entry.status = "voided"
    entry.voided_by = payload.voided_by
    entry.voided_at = datetime.utcnow()
    entry.void_reason = payload.reason

    log_action(db, "VOID", entry, payload.voided_by,
               f"Entry voided: {payload.reason or 'no reason given'}")
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}")
def delete_entry_deprecated(entry_id: int):
    """Hard delete is no longer supported. Use POST /{entry_id}/void instead."""
    raise HTTPException(
        status_code=405,
        detail="Hard delete is disabled. Use POST /api/entries/{entry_id}/void."
    )


@router.get("/audit-log/all")
def get_audit_log(
    action: Optional[str] = None,
    user: Optional[str] = None,
    short_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if user:
        q = q.filter(AuditLog.user_name == user)
    if short_id:
        q = q.filter(AuditLog.short_id == short_id)
    return q.order_by(AuditLog.timestamp.desc()).all()


@router.get("/supplier-memory/all")
def get_supplier_memory(db: Session = Depends(get_db)):
    return db.query(SupplierMemory).all()
