# AccountMaxxer

Malaysia-specific AI-assisted accounting for Accounts Payable workflows.

AccountMaxxer is a FastAPI + SQLite + React/Vite prototype for recording and
reviewing supplier purchases, returns / credit notes, supplier payments,
settlement discounts, period locks, creditor aging, and audit trails. Hermes is
kept as the agent/integration layer: chat, MCP tools, and future autonomous
accounting actions.

## What It Does

- Records purchases, credit notes / returns, and supplier payments.
- Tracks settlement discounts to GL 4200 as income.
- Maintains creditor balances and settlement-aware aging buckets.
- Supports Malaysian SST split on gross-inclusive invoice totals.
- Supports foreign-currency entries with original amount, FX rate, rate source,
  and rate lock timestamp.
- Locks accounting periods and records lock/unlock audit events.
- Keeps a full audit log for creates, voids, and period actions.
- Uses soft voids instead of hard deletes.
- Provides server-side count endpoints for dashboard/sidebar metrics.
- Exposes an MCP server for Hermes accounting tools.

## Stack

- Backend: FastAPI, SQLAlchemy, SQLite
- Frontend: React, Vite, CSS modules
- Agent integration: Hermes chat endpoint plus MCP server

## Local Run

Backend:

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

## Optional Auth

Local development remains open if no token is configured.

To protect `/api/*`, set:

```bash
ACCOUNTMAXXER_API_TOKEN=your-token
ACCOUNTMAXXER_API_USER=eugene
```

Then send:

```text
Authorization: Bearer your-token
```

The frontend can send this automatically when built/run with:

```bash
VITE_ACCOUNTMAXXER_API_TOKEN=your-token
```

When auth is enabled, `recorded_by`, `voided_by`, and `authorised_by` are derived
from the backend auth user rather than trusted from the frontend request body.

## MCP Server

The MCP server defaults to localhost-only:

```bash
cd backend
python mcp_serve.py
```

Defaults:

- MCP URL: `http://127.0.0.1:8001/mcp`
- Backend API: `http://localhost:8000/api`

Useful environment variables:

```bash
ACCOUNTING_API=http://localhost:8000/api
ACCOUNTING_API_TOKEN=your-token
MCP_HOST=127.0.0.1
MCP_PORT=8001
```

## Money And IDs

- Backend money arithmetic uses `Decimal` and SQLAlchemy `Numeric`.
- SQLite still has loose type affinity, so this is an ORM/API precision fix. A
  stricter production database should still get a proper migration.
- Transaction IDs use ULID-style sortable IDs: `TXN-<26 chars>`.

## Malaysian Accounting Notes

- Demo exchange rate: `1 INR = 0.04182 MYR`.
- Indian lakh notation: `1,00,000 = 100,000`.
- SST split assumes gross-inclusive invoice totals.
- Discount received goes to GL 4200, not against purchase expense.
- `GET /api/periods/current` uses Malaysia UTC+8 time.

### Asia Trade Centre Demo

| # | Transaction | INR | MYR |
|---|---:|---:|---:|
| 1 | Purchase | 100,000 | 4,182.00 |
| 2 | Return | 10,000 | 418.20 |
| 3 | Further purchase | 50,000 | 2,091.00 |
| - | Balance owed | 140,000 | 5,854.80 |
| 4 | Cheque paid | 135,000 | 5,645.70 |
| - | Discount received | 5,000 | 209.10 |

Final balance: `5,854.80 - 5,645.70 - 209.10 = 0.00`.

## GL Codes

| Code | Category |
|---:|---|
| 2100 | Accounts Payable |
| 4200 | Discount Received |
| 5100 | Cost of Goods Sold |
| 5200 | Utilities |
| 5300 | Repairs & Maintenance |
| 5400 | Office Supplies |
| 5500 | Transport & Logistics |
| 5600 | Professional Fees |
| 5700 | Rental & Lease |
| 5800 | Other Expenses |

## Audit Trail

- `audit_log` is append-only by API convention and protected by SQLite triggers
  against direct `UPDATE` and `DELETE`.
- Every create and void is logged with timestamp, actor, supplier, amount,
  document reference, and description.
- Period lock/unlock events are also logged.
- Voided entries remain in the database and are excluded from reports.

## Current Roadmap

Most review TODOs have been handled. The remaining major accounting upgrade is
the reversing-entry void pattern: create a counter-entry and flag both entries
instead of only using the current pragmatic soft-void status.

See `docs/HANDOFF.md` for detailed session history and verification notes.
