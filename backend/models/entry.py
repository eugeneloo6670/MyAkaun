from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base
import time, random, string

# TODO(decimal-migration): Float is used throughout for monetary fields. This is
# correct for demo/prototype use but should be migrated to Numeric(12, 2) + Pydantic
# Decimal before storing real books. Codex review item Important #8. Plan: do it in a
# focused session with Alembic migration, full report/test pass, and JSON serialization
# verified on the frontend. Not safe to mix into a multi-fix session.

def generate_short_id():
    suffix = str(int(time.time() * 1000))[-6:]
    return f"TXN-{suffix}"

class Entry(Base):
    __tablename__ = "entries"

    id              = Column(Integer, primary_key=True, index=True)
    short_id        = Column(String, unique=True, default=generate_short_id)
    date            = Column(String, nullable=False)          # YYYY-MM-DD
    month           = Column(String, nullable=False, index=True)  # YYYY-MM
    type            = Column(String, nullable=False)          # purchase | return | payment
    status          = Column(String, nullable=False, default="posted", index=True)
                      # posted | voided   (draft reserved for future maker/checker)
    supplier        = Column(String, nullable=False, index=True)
    reference       = Column(String, nullable=True)
    description     = Column(Text, nullable=True)
    gl_code         = Column(String, nullable=True)
    gl_name         = Column(String, nullable=True)
    amount          = Column(Float, nullable=False)
    sst_rate        = Column(Float, default=0)
    sst_amount      = Column(Float, default=0)
    total           = Column(Float, nullable=False)
    orig_ccy        = Column(String, default="MYR")
    orig_amount     = Column(Float, nullable=True)
    fx_rate         = Column(Float, nullable=True)
    doc_ref         = Column(String, nullable=True)           # file path or storage key
    linked_to       = Column(String, nullable=True)           # short_id of related entry
    recorded_by     = Column(String, nullable=True)
    recorded_at     = Column(DateTime, server_default=func.now())
    voided_by       = Column(String, nullable=True)
    voided_at       = Column(DateTime, nullable=True)
    void_reason     = Column(Text, nullable=True)
    # Payment-specific fields
    paid            = Column(Float, nullable=True)
    balance_owed    = Column(Float, nullable=True)
    discount_received = Column(Float, nullable=True)


class AuditLog(Base):
    """Append-only. Never expose UPDATE or DELETE on this table."""
    __tablename__ = "audit_log"

    id          = Column(Integer, primary_key=True, index=True)
    action      = Column(String, nullable=False)   # CREATE | DELETE | LOCK | UNLOCK
    entry_id    = Column(Integer, nullable=True)
    short_id    = Column(String, nullable=False)
    user_name   = Column(String, nullable=False)
    timestamp   = Column(DateTime, server_default=func.now())
    supplier    = Column(String, nullable=True)
    reference   = Column(String, nullable=True)
    entry_type  = Column(String, nullable=True)
    amount      = Column(Float, nullable=True)
    doc_ref     = Column(String, nullable=True)
    description = Column(Text, nullable=True)


class Period(Base):
    __tablename__ = "periods"

    month       = Column(String, primary_key=True)   # YYYY-MM
    locked      = Column(Boolean, default=False)
    locked_at   = Column(DateTime, nullable=True)
    locked_by   = Column(String, nullable=True)
    reason      = Column(Text, nullable=True)


class SupplierMemory(Base):
    __tablename__ = "supplier_memory"

    supplier    = Column(String, primary_key=True)
    last_gl     = Column(String, nullable=True)      # "5100|Cost of Goods Sold"
    last_ccy    = Column(String, default="MYR")
    entry_count = Column(Integer, default=0)
    last_seen   = Column(DateTime, nullable=True)
