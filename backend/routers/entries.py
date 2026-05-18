from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from database import get_db
from models.entry import Entry, AuditLog, SupplierMemory

router = APIRouter()

class EntryCreate(BaseModel):
    date: str
    type: str                          # purchase | return | payment
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
    return q.order_by(Entry.date.desc()).all()


@router.get("/{entry_id}")
def get_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.delete("/{entry_id}")
def delete_entry(entry_id: int, deleted_by: str = "System", db: Session = Depends(get_db)):
    entry = db.query(Entry).filter_by(id=entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    from models.entry import Period
    period = db.query(Period).filter_by(month=entry.month).first()
    if period and period.locked:
        raise HTTPException(status_code=400, detail=f"Period {entry.month} is locked.")
    log_action(db, "DELETE", entry, deleted_by, "Entry deleted")
    db.delete(entry)
    db.commit()
    return {"deleted": entry_id}


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
