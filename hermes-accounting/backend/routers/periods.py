from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from database import get_db
from models.entry import Period, AuditLog

router = APIRouter()

class PeriodLockRequest(BaseModel):
    month: str
    locked: bool
    reason: str
    authorised_by: str


@router.get("/")
def list_periods(db: Session = Depends(get_db)):
    return db.query(Period).order_by(Period.month.desc()).all()


@router.post("/lock")
def set_period_lock(payload: PeriodLockRequest, db: Session = Depends(get_db)):
    period = db.query(Period).filter_by(month=payload.month).first()
    if not period:
        period = Period(month=payload.month)
        db.add(period)

    period.locked = payload.locked
    period.reason = payload.reason
    action = "LOCK" if payload.locked else "UNLOCK"

    if payload.locked:
        period.locked_at = datetime.utcnow()
        period.locked_by = payload.authorised_by
    else:
        period.locked_at = None
        period.locked_by = None

    log = AuditLog(
        action=action,
        short_id=payload.month,
        user_name=payload.authorised_by,
        supplier="—",
        reference="—",
        entry_type="period",
        amount=0,
        description=f"Period {action.lower()}ed: {payload.month}. {payload.reason}"
    )
    db.add(log)
    db.commit()
    return {"month": payload.month, "locked": payload.locked, "action": action}


@router.get("/{month}/status")
def get_period_status(month: str, db: Session = Depends(get_db)):
    period = db.query(Period).filter_by(month=month).first()
    if not period:
        return {"month": month, "locked": False}
    return period
