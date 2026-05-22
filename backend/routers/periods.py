from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from database import get_db
from models.entry import Period, AuditLog
from auth import AuthContext, require_api_auth

router = APIRouter()
MALAYSIA_TZ = timezone(timedelta(hours=8), name="Asia/Kuala_Lumpur")

class PeriodLockRequest(BaseModel):
    month: str
    locked: bool
    reason: str
    authorised_by: str | None = None


@router.get("/")
def list_periods(db: Session = Depends(get_db)):
    return db.query(Period).order_by(Period.month.desc()).all()


@router.post("/lock")
def set_period_lock(
    payload: PeriodLockRequest,
    auth: AuthContext = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    period = db.query(Period).filter_by(month=payload.month).first()
    if not period:
        period = Period(month=payload.month)
        db.add(period)

    period.locked = payload.locked
    period.reason = payload.reason
    action = "LOCK" if payload.locked else "UNLOCK"
    actor = auth.actor(payload.authorised_by or "System")

    if payload.locked:
        period.locked_at = datetime.utcnow()
        period.locked_by = actor
    else:
        period.locked_at = None
        period.locked_by = None

    log = AuditLog(
        action=action,
        short_id=payload.month,
        user_name=actor,
        supplier="—",
        reference="—",
        entry_type="period",
        amount=0,
        description=f"Period {action.lower()}ed: {payload.month}. {payload.reason}"
    )
    db.add(log)
    db.commit()
    return {"month": payload.month, "locked": payload.locked, "action": action}


@router.get("/current")
def get_current_period(db: Session = Depends(get_db)):
    """Returns the current month's period status. Always returns a value (locked=False if no record)."""
    month = datetime.now(MALAYSIA_TZ).strftime("%Y-%m")
    period = db.query(Period).filter_by(month=month).first()
    if not period:
        return {"month": month, "locked": False}
    return period


@router.get("/{month}/status")
def get_period_status(month: str, db: Session = Depends(get_db)):
    period = db.query(Period).filter_by(month=month).first()
    if not period:
        return {"month": month, "locked": False}
    return period
