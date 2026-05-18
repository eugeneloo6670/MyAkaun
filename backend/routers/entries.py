from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel
from database import get_db
from models.entry import Entry, AuditLog, SupplierMemory

router = APIRouter()

EntryType = Literal["purchase", "return", "payment"]

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
            if payload.paid + payload.discount_received > payload.balance_owed + 0.005:
                raise HTTPException(
                    status_code=400,
                    detail="paid + discount_received exceeds balance_owed (overpayment must be handled explicitly)",
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
def create_entry(payload: EntryCreate, db: Session = Depends(get_db)):
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
    db.commit()
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
        q = q.filter(Entry.doc_ref == None)
    if linked_to:
        q = q.filter(Entry.linked_to == linked_to)
    if status:
        q = q.filter(Entry.status == status)
    elif not include_voided:
        # Default: hide voided entries from the ledger view.
        q = q.filter(Entry.status != "voided")
    return q.order_by(Entry.date.desc()).all()


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
