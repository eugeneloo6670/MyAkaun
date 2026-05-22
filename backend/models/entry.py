from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base
import secrets
import time

MONEY_TYPE = Numeric(14, 2, asdecimal=True)
RATE_TYPE = Numeric(18, 6, asdecimal=True)
PERCENT_TYPE = Numeric(5, 2, asdecimal=True)

def generate_short_id():
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    timestamp_ms = int(time.time() * 1000)

    encoded_time = ""
    value = timestamp_ms
    for _ in range(10):
        encoded_time = alphabet[value % 32] + encoded_time
        value //= 32

    random_part = "".join(secrets.choice(alphabet) for _ in range(16))
    return f"TXN-{encoded_time}{random_part}"

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
    amount          = Column(MONEY_TYPE, nullable=False)
    sst_rate        = Column(PERCENT_TYPE, default=0)
    sst_amount      = Column(MONEY_TYPE, default=0)
    total           = Column(MONEY_TYPE, nullable=False)
    orig_ccy        = Column(String, default="MYR")
    orig_amount     = Column(MONEY_TYPE, nullable=True)
    fx_rate         = Column(RATE_TYPE, nullable=True)
    rate_source     = Column(String, nullable=True)
    rate_locked_at  = Column(DateTime, nullable=True)
    doc_ref         = Column(String, nullable=True)           # file path or storage key
    linked_to       = Column(String, nullable=True)           # short_id of related entry
    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    idempotency_hash = Column(String, nullable=True)
    recorded_by     = Column(String, nullable=True)
    recorded_at     = Column(DateTime, server_default=func.now())
    voided_by       = Column(String, nullable=True)
    voided_at       = Column(DateTime, nullable=True)
    void_reason     = Column(Text, nullable=True)
    # Payment-specific fields
    paid            = Column(MONEY_TYPE, nullable=True)
    balance_owed    = Column(MONEY_TYPE, nullable=True)
    discount_received = Column(MONEY_TYPE, nullable=True)


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
    amount      = Column(MONEY_TYPE, nullable=True)
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
