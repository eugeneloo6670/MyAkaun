from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models.entry import Entry, AuditLog
from money import money_sum
from services.hermes_bridge import query_hermes
import json

router = APIRouter()


class HermesQueryRequest(BaseModel):
    message: str
    month: Optional[str] = None
    supplier: Optional[str] = None
    user: Optional[str] = "User"


def build_context(entries: list, audit_log: list) -> str:
    """
    Builds a structured English context block injected into every Hermes query.
    Hermes reads this alongside its SOUL.md and accounting skills.
    """
    total = money_sum(e.total for e in entries if e.type == "purchase")
    missing_docs = [e.short_id for e in entries if not e.doc_ref]
    suppliers = list(set(e.supplier for e in entries))

    lines = [
        "=== HERMES ACCOUNTING CONTEXT ===",
        f"Entries loaded: {len(entries)}",
        f"Suppliers: {', '.join(suppliers)}",
        f"Total purchases (gross): MYR {total:,.2f}",
        f"Missing document references: {len(missing_docs)} — {', '.join(missing_docs) if missing_docs else 'none'}",
        "",
        "Recent entries (latest 10):",
    ]
    for e in sorted(entries, key=lambda x: x.date, reverse=True)[:10]:
        lines.append(
            f"  {e.short_id} | {e.date} | {e.type.upper()} | {e.supplier} | "
            f"{e.reference or 'no-ref'} | MYR {abs(e.total):,.2f} | "
            f"doc={'YES' if e.doc_ref else 'MISSING'} | GL {e.gl_code}"
        )

    lines += [
        "",
        "Recent audit events:",
    ]
    for a in sorted(audit_log, key=lambda x: str(x.timestamp), reverse=True)[:5]:
        lines.append(f"  [{a.action}] {a.short_id} by {a.user_name} — {a.description or ''}")

    lines.append("=== END CONTEXT ===")
    return "\n".join(lines)


@router.post("/query")
async def hermes_query(payload: HermesQueryRequest, db: Session = Depends(get_db)):
    """
    Main chat endpoint. Injects ledger context into Hermes and streams response.
    Called by HermesChatBar.jsx in the frontend.
    """
    q = db.query(Entry)
    if payload.month:
        q = q.filter(Entry.month == payload.month)
    if payload.supplier:
        q = q.filter(Entry.supplier == payload.supplier)
    entries = q.all()

    audit = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(20).all()
    context = build_context(entries, audit)

    return StreamingResponse(
        query_hermes(payload.message, context),
        media_type="text/event-stream"
    )


@router.post("/nightly-log")
async def receive_nightly_log(body: dict, db: Session = Depends(get_db)):
    """
    Hermes nightly skill posts its summary here after running.
    Stored in audit log for traceability.
    """
    log = AuditLog(
        action="NIGHTLY_REVIEW",
        short_id="NIGHTLY",
        user_name="Hermes (cron)",
        description=body.get("summary", "Nightly review completed"),
    )
    db.add(log)
    db.commit()
    return {"status": "logged"}
