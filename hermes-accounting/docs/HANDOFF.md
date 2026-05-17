# Hermes Accounting — Handoff Document
# Feed this to a new Claude session to resume work

## Project Summary
Building a Malaysia-specific AI accounting system integrating the Hermes Agent
(github.com/nousresearch/hermes-agent). Started as a simple purchase/receipt recorder,
evolved into a full audit-trail system with Hermes AI integration.

## What Has Been Built (in order)

### v1 — Basic purchase recorder
- Date, supplier, reference, GL category (5100–5800), amount, SST (0/6/8/10%)
- Ledger tab with filters
- Month-end GL breakdown
- Contextual Hermes notes after each entry

### v2 — Credit notes and payments
- Entry type selector: Purchase | Credit note | Return | Payment to supplier
- Credit notes record as negative amounts linked to original purchase
- Payment entries capture amount paid vs balance owed
- Settlement discount auto-calculated → GL 4200 (income, not expense reduction)
- Creditors tab: live running balance per supplier
- Aged payables: 0–30d, 31–60d, 61–90d, 90d+ buckets

### v3 — Audit trail
- Transaction IDs: TXN-XXXXXX format
- Kanban board: Purchases | Credit notes | Payments | Discounts columns
- Transaction linkage map: bidirectional links (credit notes → original purchases)
- Audit log: immutable timestamped CREATE/DELETE/LOCK/UNLOCK events
- CSV export of audit log

### v4 — Document references + period locking
- Supporting document reference field on every entry
- Document status: green tick (filed) / red flag (missing) on kanban cards
- Month-end lock/unlock with reason and authorised-by field
- Lock events written to audit log
- Record-button disabled when period is locked
- Ledger shows lock icon instead of delete button for locked periods
- Supplier autocomplete with last-used GL code memory
- Foreign currency: separate numeric fields for original amount and FX rate
- FX auto-calculates MYR amount
- "Recorded by" field → shown on kanban cards and audit log
- Missing doc count shown in ledger metrics and month-end metrics
- Periods tab: shows open/locked status, missing doc count, lock/unlock form

### v5 (current) — Desktop shell UI
- Three-column layout: left nav (180px) | main content | right detail panel (240px)
- Right panel shows full entry detail on click:
  - Document status alert (red if missing)
  - All fields including FX details
  - Transaction linkage chips
  - Audit trail timeline
  - Recorded-by avatar
- Hermes chat bar at bottom of main panel (persistent)
- Live streaming response from Hermes agent

## Architecture

### Backend (FastAPI + Python)
- main.py — app entry, CORS, router registration
- database.py — SQLAlchemy, SQLite (dev) / PostgreSQL (prod)
- models/entry.py — Entry, AuditLog, Period, SupplierMemory
- routers/entries.py — CRUD with audit logging, supplier memory
- routers/periods.py — lock/unlock with audit
- routers/reports.py — month-end, creditors, aged payables
- routers/hermes.py — chat endpoint + nightly log receiver
- services/hermes_bridge.py — streams from Hermes gateway
- mcp_serve.py — MCP server exposing accounting as tools

### Frontend (React + Vite)
- Shell.jsx — three-column layout, view routing
- HermesChatBar.jsx — streaming chat with Hermes agent
- api/client.js — axios wrapper

### Hermes Integration (3 levels)
1. Chat bar → /api/hermes/query → hermes_bridge → streams response
2. MCP server (port 8001) → Hermes calls record_entry, query_ledger etc autonomously
3. Cron: nightly-accounting-review skill at 23:00 → WhatsApp summary

### Hermes Config Files
- hermes/SOUL.md — Malaysian accounting persona and rules
- hermes/config.yaml — MCP server URL, skill dirs, cron, model
- hermes/skills/SKILL.md — Master accounting skill (GL codes, entry types, audit rules)
- hermes/skills/nightly-review/SKILL.md — Nightly cron skill

## Key Business Logic

### Settlement Discount
When supplier accepts less than full balance:
  discount_received = balance_owed - amount_paid
  → GL 4200 (income), NOT a reduction in purchase cost
  Requires supplier written confirmation as supporting document.

### Indian Lakh Notation
1,00,000 = 100,000 (not 1 million)
2,00,000 = 200,000

### Asia Trade Centre Demo (INR→MYR @ 0.04182)
TXN-001001: Purchase INR 1,00,000 → MYR 4,182.00 (GL 5100)
TXN-001002: Return INR 10,000 → MYR 418.20 (GL 5100, links to TXN-001001)
TXN-001003: Purchase INR 50,000 → MYR 2,091.00 (GL 5100, NO DOC - intentional)
TXN-001004: Payment INR 1,35,000 → MYR 5,647.70 + discount MYR 209.10 (GL 4200)

### GL Codes
2100 Accounts Payable | 4200 Discount Received (income)
5100 COGS | 5200 Utilities | 5300 Repairs | 5400 Office Supplies
5500 Transport | 5600 Professional Fees | 5700 Rental | 5800 Other

## What Needs Building Next
- [ ] Ledger.jsx — full entry table with filters, wired to /api/entries
- [ ] RecordForm.jsx — the entry form as a proper React component
- [ ] Creditors.jsx — creditor balances wired to /api/reports/creditors
- [ ] MonthEnd.jsx — GL breakdown wired to /api/reports/month-end/{month}
- [ ] KanbanTrail.jsx — kanban board wired to /api/entries
- [ ] AuditLog.jsx — wired to /api/entries/audit-log/all
- [ ] Periods.jsx — wired to /api/periods
- [ ] RightPanel.jsx — full detail panel with audit timeline
- [ ] Sidebar.jsx — nav with live counts
- [ ] Document upload — base64 image storage or S3 presigned URLs
- [ ] Maker/checker approval workflow
- [ ] PDF audit report generation
- [ ] LHDN e-invoice submission via MyInvois API
- [ ] SST treatment skill (lhdn-einvoicing/SKILL.md, sst-treatment/SKILL.md)
- [ ] Multi-tenant support (per-company database separation)

## Malaysian Context
- LHDN e-Invoice required for businesses above RM 150k turnover
- MyInvois system: document types 01=Invoice, 02=Credit Note, 11=Self-billed
- SST: 6% or 8% service tax, 10% sales tax
- Professional fees (GL 5600): usually 8% service tax — verify supplier SST registration
- Chinese receipts: 收据 = receipt (non-tax), 发票 = invoice (tax)
- 发票 required for LHDN compliance, not 收据

## Competitors Researched
- Tofu (gotofu.com) — AI invoice extraction, Xero/QBO integration, USD 79/month
- Access UBS Evo BSM (actiwise.com.my) — Malaysian property management, LHDN compliant, AI chatbot only
- Both are static products; Hermes gives us an evolving agent that acts autonomously
