"""
MCP Server for Hermes Accounting.
Run this as a separate process: python mcp_serve.py --port 8001

Hermes config to add:
  hermes config set mcp.servers.hermes-accounting http://localhost:8001/mcp

Once connected, Hermes can:
  - Record entries autonomously (e.g. from WhatsApp receipt photos)
  - Query balances and reports
  - Lock/unlock periods
  - Run nightly reviews
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any
import uvicorn, httpx, json

ACCOUNTING_API = "http://localhost:8000/api"

app = FastAPI(title="Hermes Accounting MCP Server")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# MCP Tool registry
TOOLS = {
    "record_entry": {
        "description": "Record a new purchase, credit note, or payment entry in the accounting ledger",
        "parameters": {
            "date": "string — YYYY-MM-DD",
            "type": "string — purchase | return | payment",
            "supplier": "string",
            "amount": "number — MYR amount before SST",
            "total": "number — MYR total including SST",
            "gl_code": "string — e.g. 5100",
            "gl_name": "string — e.g. Cost of Goods Sold",
            "reference": "string (optional) — invoice/CN/cheque number",
            "doc_ref": "string (optional) — scanned file path",
            "orig_ccy": "string (optional) — INR, USD, MYR etc",
            "orig_amount": "number (optional)",
            "fx_rate": "number (optional)",
            "description": "string (optional)",
            "recorded_by": "string (optional, default: Hermes)",
            "sst_rate": "number (optional, default: 0)",
            "sst_amount": "number (optional, default: 0)",
            "paid": "number (optional, for payment type)",
            "balance_owed": "number (optional, for payment type)",
            "discount_received": "number (optional, for payment type)",
            "linked_to": "string (optional) — short_id of related entry",
        }
    },
    "query_ledger": {
        "description": "Query entries from the ledger with optional filters",
        "parameters": {
            "month": "string (optional) — YYYY-MM",
            "supplier": "string (optional)",
            "type": "string (optional) — purchase | return | payment",
            "missing_docs": "boolean (optional) — filter to entries missing documents",
        }
    },
    "get_creditor_balance": {
        "description": "Get the outstanding balance and aged payables for a supplier",
        "parameters": {
            "supplier": "string"
        }
    },
    "get_month_end_summary": {
        "description": "Get the full month-end GL summary including balances and missing document count",
        "parameters": {
            "month": "string — YYYY-MM"
        }
    },
    "get_aged_payables": {
        "description": "Get all overdue payables across all suppliers — used for nightly review",
        "parameters": {}
    },
    "set_period_lock": {
        "description": "Lock or unlock an accounting period to prevent/allow entry changes",
        "parameters": {
            "month": "string — YYYY-MM",
            "locked": "boolean",
            "reason": "string",
            "authorised_by": "string",
        }
    },
}


class MCPCallRequest(BaseModel):
    tool: str
    params: dict = {}


@app.get("/mcp/tools")
def list_tools():
    """Hermes calls this on startup to discover available tools."""
    return {"tools": TOOLS}


@app.post("/mcp/call")
async def call_tool(request: MCPCallRequest):
    """Hermes calls this to invoke a tool."""
    tool = request.tool
    params = request.params

    async with httpx.AsyncClient(timeout=30) as client:

        if tool == "record_entry":
            r = await client.post(f"{ACCOUNTING_API}/entries/", json=params)
            return r.json()

        elif tool == "query_ledger":
            r = await client.get(f"{ACCOUNTING_API}/entries/", params=params)
            return r.json()

        elif tool == "get_creditor_balance":
            supplier = params.get("supplier")
            r = await client.get(f"{ACCOUNTING_API}/reports/creditors")
            creditors = r.json()
            match = next((c for c in creditors if c["supplier"] == supplier), None)
            return match or {"error": f"Supplier '{supplier}' not found"}

        elif tool == "get_month_end_summary":
            month = params.get("month")
            r = await client.get(f"{ACCOUNTING_API}/reports/month-end/{month}")
            return r.json()

        elif tool == "get_aged_payables":
            r = await client.get(f"{ACCOUNTING_API}/reports/aged-payables")
            return r.json()

        elif tool == "set_period_lock":
            r = await client.post(f"{ACCOUNTING_API}/periods/lock", json=params)
            return r.json()

        else:
            return {"error": f"Unknown tool: {tool}"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
