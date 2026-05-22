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
- Transaction IDs: TXN-XXXXXX format (stored on backend as `short_id`)
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

### v5 — Desktop shell UI
- Three-column layout: left nav (180px) | main content | right detail panel (280px)
- Right panel shows full entry detail on click:
  - Document status alert (red if missing)
  - All fields including FX details
  - Transaction linkage chips
  - Audit trail timeline
  - Recorded-by avatar
- Hermes chat bar at bottom of main panel (persistent)
- Live streaming response from Hermes agent

### v6 — Frontend AP component build-out
Built as proper modular React components matching v5 spec. All use plain CSS
modules with consistent design tokens (cool neutrals, teal accent, amber for
warnings, red for missing docs / overdue).

Files under `frontend/src/components/`:
- RecordForm/ — entry form (Purchase | Credit Note | Return | Payment)
- Sidebar/ — 180px left rail with live counts and period chip
- Ledger/ — entry table with filters, metrics, CSV export
- Creditors/ — AP aging buckets with expandable per-supplier drawer
- RightPanel/ — 280px detail panel with FX, linked TXNs, audit timeline

### v7 (current) — Backend alignment + integration
The v6 components were initially written against an assumed API contract that
did not match the real backend. Session 3 (this one) reconciled the two:

**Backend additions** (small, non-breaking):
- `/api/periods/current` — returns current month's period status
- `/api/entries/audit-log/all?short_id=X` — added `short_id` filter
- `/api/entries/?linked_to=X` — added `linked_to` filter for linked transactions

**Component patches** (substantial):
- All five v6 components switched from `import { api }` to `import api`
  (named to default import, since client.js exports `api` as default)
- All references to `txn_id` → `short_id` (real backend field name)
- All references to `amount_myr` → `total` (real backend field)
- All references to `fx_currency`/`fx_original` → `orig_ccy`/`orig_amount`
- All references to `amount_paid` → `paid`, `discount_amount` → `discount_received`
- Aging keys: flat `aging_X_X` → nested `aged.{current, d30, d60, d90plus}`
- RecordForm: "Credit Note" UI button now maps to backend `type=return`
  (backend only supports purchase|return|payment; functionally identical reversal)
- RecordForm: GL `gl_name` derived client-side from `gl_code` lookup
- RecordForm: SST split derived as `net = gross / (1 + rate)`; sends `amount`,
  `sst_amount`, and `total` correctly
- RecordForm: payment_method goes into `description` (backend has no dedicated field)
- Sidebar: count endpoints don't exist; counts derived client-side from lists
- Ledger: backend supports limited filters (month, supplier, type, missing_docs);
  date range, GL filter, doc_status=filed, and free-text search done client-side
- Ledger: pagination done client-side (slice on filtered list)
- Creditors: `/api/reports/creditors?supplier=X` filter unsupported; fetch all
  and filter client-side
- RecordForm: added `prefill` prop. When `{action: 'pay', supplier}` is passed,
  starts in payment mode with supplier pre-filled (used by Creditors → Pay flow)

**Frontend stubs added** so `npm run dev` doesn't error:
- ComingSoon.jsx — shared placeholder
- MonthEnd.jsx, KanbanTrail.jsx, AuditLog.jsx, Periods.jsx — all stub-only,
  point to their target backend endpoints, ready for future build-out

**Shell.jsx rewritten** to:
- Use v6 component prop names (`onNavigate`, `refreshTrigger`, `onSelectEntry`,
  `onSelectSupplier`)
- Handle the Creditors → Pay flow by storing `paymentPrefill` state
- Mount HermesChatBar in the middle column at the bottom
- Use 180/1fr/280 grid columns

## Architecture

### Backend (FastAPI + Python)
- main.py — app entry, CORS, router registration
- database.py — SQLAlchemy, SQLite (dev) / PostgreSQL (prod)
- models/entry.py — Entry, AuditLog, Period, SupplierMemory
- routers/entries.py — CRUD with audit logging, supplier memory
  - new query params: `linked_to`, `short_id` (on audit-log endpoint)
- routers/periods.py — lock/unlock with audit
  - new endpoint: `GET /current`
- routers/reports.py — month-end, creditors, aged payables
- routers/hermes.py — chat endpoint + nightly log receiver
- services/hermes_bridge.py — streams from Hermes gateway
- mcp_serve.py — MCP server exposing accounting as tools

### Frontend (React + Vite)
- Shell.jsx — three-column layout, view routing (v7 wired)
- HermesChatBar.jsx — streaming chat with Hermes agent (unchanged)
- api/client.js — axios wrapper; named exports for all endpoints + default `api`
  - new exports: `getCurrentPeriod`, `getEntry`
- components/RecordForm/ — v6 + v7 patches
- components/Sidebar/ — v6 + v7 patches
- components/Ledger/ — v6 + v7 patches
- components/Creditors/ — v6 + v7 patches
- components/RightPanel/ — v6 + v7 patches
- components/MonthEnd.jsx, KanbanTrail.jsx, AuditLog.jsx, Periods.jsx — stubs
- components/ComingSoon.jsx — shared stub component

### Hermes Integration (3 levels) — unchanged
1. Chat bar → /api/hermes/query → hermes_bridge → streams response
2. MCP server (port 8001) → Hermes calls record_entry, query_ledger etc autonomously
3. Cron: nightly-accounting-review skill at 23:00 → WhatsApp summary

## Backend API contract (REAL, verified against routers/*.py)

### Entries
- `GET /api/entries/` — params: `month, supplier, type, missing_docs, linked_to`
  Returns array of Entry objects
- `POST /api/entries/` — body: EntryCreate (see entries.py for full Pydantic model)
- `GET /api/entries/{id}` — get one by integer id
- `DELETE /api/entries/{id}` — soft-delete (writes audit log)
- `GET /api/entries/audit-log/all` — params: `action, user, short_id`
- `GET /api/entries/supplier-memory/all` — returns
  `[{supplier, last_gl: "5100|Cost of Goods Sold", last_ccy, entry_count, last_seen}]`

### Reports
- `GET /api/reports/creditors` — returns
  `[{supplier, gross_purchases, returns, payments, discounts, balance,
     aged: {current, d30, d60, d90plus}, missing_docs, transaction_count}]`
  Sorted by `abs(balance)` desc. No supplier filter (frontend filters client-side).
- `GET /api/reports/month-end/{month}` — full GL breakdown
- `GET /api/reports/aged-payables` — overdue summary

### Periods
- `GET /api/periods/` — list all
- `GET /api/periods/current` — current month status (new in v7)
- `GET /api/periods/{month}/status` — specific month
- `POST /api/periods/lock` — body: `{month, locked, reason, authorised_by}`

## Entry data shape (sent on POST, returned on GET)

```js
{
  id: 42,                              // int, auto-increment
  short_id: "TXN-123456",              // public id, last 6 digits of Unix ms
  date: "2026-05-18",                  // YYYY-MM-DD
  month: "2026-05",                    // YYYY-MM (auto-derived from date)
  type: "purchase",                    // purchase | return | payment
  supplier: "Asia Trade Centre",
  reference: "INV-0042",
  description: null,
  gl_code: "5100",
  gl_name: "Cost of Goods Sold",
  amount: 100.00,                      // net (excl SST)
  sst_rate: 6,
  sst_amount: 6.00,
  total: 106.00,                       // gross — this is what UI shows
  orig_ccy: "INR",
  orig_amount: 100000,                 // in original currency
  fx_rate: 0.04182,
  doc_ref: "scan-001.pdf",             // or null = missing doc, red flag
  linked_to: "TXN-001001",             // short_id of original (for returns/CN)
  recorded_by: "eugene",
  recorded_at: "...",                  // server-set timestamp
  // Payment-only fields:
  paid: null,
  balance_owed: null,
  discount_received: null,             // → GL 4200
}
```

## Key Business Logic

### Settlement Discount
When supplier accepts less than full balance:
  discount_received = balance_owed - amount_paid
  → GL 4200 (income), NOT a reduction in purchase cost
  Requires supplier written confirmation as supporting document.

### Credit Note vs Return (UI vs backend)
- UI shows 4 buttons: Purchase | Credit Note | Return | Payment
- Backend has 3 types: purchase | return | payment
- "Credit Note" UI button maps to backend `type=return` on submit
- Same backend handling; distinction is purely for UX clarity in the form

### Indian Lakh Notation
1,00,000 = 100,000 (not 1 million)
2,00,000 = 200,000

### Asia Trade Centre Demo (INR→MYR @ 0.04182)
TXN-001001: Purchase INR 1,00,000 → MYR 4,182.00 (GL 5100)
TXN-001002: Return   INR 10,000   → MYR   418.20 (GL 5100, links to TXN-001001)
TXN-001003: Purchase INR 50,000   → MYR 2,091.00 (GL 5100, NO DOC - intentional)
TXN-001004: Payment  INR 1,35,000 → MYR 5,645.70 + discount MYR 209.10 (GL 4200)

Arithmetic check (Codex review confirmed):
  Gross purchases:  4,182.00 + 2,091.00 = 6,273.00
  Returns:                              −  418.20
  Outstanding:                            5,854.80
  Payment + discount: 5,645.70 + 209.10 = 5,854.80   ✅ balance closes to 0

### GL Codes
2100 Accounts Payable | 4200 Discount Received (income)
5100 COGS | 5200 Utilities | 5300 Repairs | 5400 Office Supplies
5500 Transport | 5600 Professional Fees | 5700 Rental | 5800 Other

## What Needs Building Next (priority order)

### Cleanup
- [ ] **Delete `hermes-accounting/` folder at repo root** — it's a duplicate of
  the entire project from before files were moved up one level. Confuses readers;
  contains outdated copies of README, SETUP, HANDOFF, and all backend/frontend.

### High priority — get the app actually running
- [ ] Run `npm install && npm run dev` in frontend/ — verify build succeeds
- [ ] Start backend with `uvicorn main:app --reload` in backend/
- [ ] Smoke-test: create one purchase, view in ledger, view detail in right panel
- [ ] Fix anything that breaks on first run (likely styling clashes between
  v6 CSS modules and the existing CSS variable scheme used by HermesChatBar)

### Build out remaining views (currently stubs)
- [ ] **KanbanTrail.jsx** — paper-trail kanban (Purchases | CN/Return | Payments
  | Discounts columns). Wire to `getEntries()`.
- [ ] **MonthEnd.jsx** — GL breakdown per period, wired to
  `/api/reports/month-end/{month}`. Include month selector.
- [ ] **AuditLog.jsx** — append-only log view, amber for period events,
  CSV export. Wired to `getAuditLog()`.
- [ ] **Periods.jsx** — lock/unlock UI with confirmation modal. Wired to
  `getPeriods()` + `setPeriodLock()`.

### Medium priority
- [ ] Maker/checker approval workflow — adds `status` column
  (draft → pending_approval → posted → voided) + second user role.
  Requires backend schema migration.
- [ ] Document upload — base64 image storage OR S3 presigned URLs; OCR via Hermes
- [ ] Void entry action — currently RightPanel has the button but no handler

### Lower priority / future workstreams
- [ ] LHDN e-invoice skill — `hermes/skills/lhdn-einvoicing/SKILL.md`
- [ ] SST treatment skill — `hermes/skills/sst-treatment/SKILL.md`
- [ ] PDF audit report generation
- [ ] AR module (separate session): sales invoices, customer receipts, debtors,
  GL 1200/4100/4300
- [ ] Multi-tenant support (per-company database separation)
- [ ] AI-powered chart of accounts customization per client

## Known Caveats (read before debugging)

1. **Field name asymmetry**: backend uses `short_id`/`total`/`orig_ccy`/`orig_amount`;
   if a component bug surfaces, this is the first place to look. The v7 patches
   should have caught all of these but spot any with grep:
   `grep -rE "txn_id|amount_myr|fx_currency|fx_original" frontend/src/components/`

2. **The frontend's "Credit Note" type is virtual** — backend never sees it; UI
   maps it to `type=return` before submit. If you add a 5th button, decide
   whether the backend needs a real new type or another virtual mapping.

3. **Backend `creditors` endpoint returns ALL suppliers, even fully-settled ones**
   (balance = 0). Creditors.jsx filters these out client-side. If you change
   that filter, also update the count shown in Sidebar.

4. **Period locking is enforced at POST time** by the backend
   (HTTPException 400 if locked). The frontend's pre-check is a UX nicety;
   never assume it's the only protection.

5. **No write tests anywhere yet.** First thing to add when the app runs.

## Malaysian Context — unchanged
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

## Design System Notes (for v6+ components)

Consistent CSS variables across all v6 components (scoped via CSS modules,
do NOT leak to global scope):

```css
--bg: #fafbfc;            /* page background */
--surface: #ffffff;       /* card/panel background */
--border: #e3e7ec;        /* hairline divider */
--border-strong: #c8cfd6; /* input borders */
--ink: #1a2530;           /* primary text */
--ink-soft: #5a6672;      /* secondary text */
--ink-mute: #8a929b;      /* tertiary text / labels */
--accent: #0f766e;        /* teal — primary action */
--accent-soft: #d1faf4;
--amber: #b45309;         /* warnings, period lock */
--amber-soft: #fef3c7;
--red: #b91c1c;           /* missing docs, overdue */
--red-soft: #fee2e2;
--green: #166534;         /* docs filed */
```

HermesChatBar.jsx uses a different scheme (`var(--color-text-primary)` etc).
At some point the two should align — either give v6 components access to the
same global variables, or migrate HermesChatBar to the new scheme. Not urgent;
not broken.

Typography: native system stack (-apple-system, Segoe UI, etc).
Numeric columns: `font-variant-numeric: tabular-nums`.
Code/IDs: `"SF Mono", Menlo, Consolas, monospace`.

Avoid: gradients, decorative shadows, color animations, custom fonts.
This is an audit tool — restraint signals trustworthiness.

## Session Log

- 2026-05-17 (session 1): RecordForm.jsx + module.css built. Backend assumed
  complete per v5.
- 2026-05-18 (session 2): Sidebar, Ledger, Creditors, RightPanel all built.
  HANDOFF.md updated. Files uploaded to GitHub.
- 2026-05-18 (session 3, this one): Filesystem MCP access set up. Discovered
  v6 components were written against an assumed API contract that didn't match
  reality. Patched:
  - Backend: 3 small additions (linked_to filter, short_id filter,
    /periods/current endpoint)
  - Frontend: all 5 v6 components rewritten to use real backend field names
    and endpoints, plus client.js helpers
  - Added stubs for MonthEnd / KanbanTrail / AuditLog / Periods so app can build
  - Rewrote Shell.jsx to wire everything together
  - Added `prefill` prop to RecordForm for Creditors → Pay flow
  - All files validated for JSX/Python syntax. App should now run on
    `npm run dev`, modulo whatever runtime issues a first-time test surfaces.
  - **Pending manual action: delete `hermes-accounting/` duplicate folder.**

- 2026-05-18 (session 4): First successful runtime. Discovered
  `declarative_base()` was called twice (database.py and entry.py creating
  separate Bases) which meant `Base.metadata.create_all()` never registered
  the Entry/AuditLog/Period/SupplierMemory tables. Fixed by importing Base
  from database.py in entry.py. Also created `index.html`, `src/main.jsx`,
  `src/index.css`, and `vite.config.js` (none existed; Vite couldn't find
  an entry point). Discovered the hard-delete vs soft-delete mismatch in
  Codex review but session ended before fix.
  Also deleted the duplicate `hermes-accounting/` folder.

- 2026-05-18 (session 5): Codex code review applied. Critical and
  Important fixes landed.

  **Critical**
  - Hard delete → soft delete via status column. New endpoint
    `POST /api/entries/{id}/void` accepts `{voided_by, reason?}`. The Entry
    table gained `status` ("posted" | "voided"; "draft" reserved for future
    maker/checker), `voided_by`, `voided_at`, `void_reason`. `DELETE
    /api/entries/{id}` now returns 405. All reports filter `status != "voided"`
    by default. `list_entries` accepts `include_voided=true` for audit views.
    RightPanel shows a void banner and hides the void button on voided rows.

  **Important — accounting integrity**
  - Server-side type/sign/linkage validation: `EntryCreate.type` is now
    `Literal["purchase", "return", "payment"]`. New `validate_entry_invariants`
    enforces: purchase total > 0, requires gl_code, no linked_to; return total
    < 0, requires linked_to pointing to a non-voided same-supplier purchase;
    payment requires `paid > 0` and explicit `balance_owed`; discount cannot be
    negative, cannot exceed balance, paid+discount cannot exceed balance.
  - Payment-balance race fix: RecordForm tracks `balanceState`
    (idle/loading/loaded/failed). Submit is blocked unless balanceState ===
    'loaded'. `buildPayload` throws if called for a payment without a loaded
    balance — defense in depth.
  - SST input label changed to "Amount incl. SST (MYR)" to remove gross-vs-net
    ambiguity.
  - Asia Trade Centre demo: arithmetic corrected from 5,647.70 to 5,645.70 in
    HANDOFF.md and README.md. Code unchanged (documentation bug only).

  **Important — UX**
  - RightPanel `payment_method` display: derived from `description`
    ("Payment via cheque" → "cheque"). Field was previously read from a
    non-existent `entry.payment_method` and never displayed.
  - RightPanel linked entries: now bidirectional. Fetches both children
    (entries that link TO this one) and parent (the entry this one links TO).
  - RightPanel audit timeline now recognises `VOID` action with red dot.
  - Updated RightPanel hint text so it no longer claims voiding creates a
    reversing entry (it doesn't, in this implementation).

  **Deferred to next focused session** — see Codex review TODOs below.

- 2026-05-21 (session 6): Second Codex review applied, then end-to-end
  runtime testing.

  **Codex second-review fixes (landed as 3 PRs)**
  - `.gitignore` added; untracked node_modules + __pycache__ + *.db that had
    been accidentally committed in v8 (~2700 files of bloat).
  - Void-chain protection (Codex Critical): `void_entry()` now rejects voiding
    any entry that has non-voided children linking to it, listing the blocking
    short_ids. Prevents the corruption where a voided parent disappears from
    reports but its returns/payments remain, producing negative balances.
  - Startup migrations: `backend/migrations.py` added — PRAGMA table_info check
    + ALTER TABLE for columns missing on an existing DB. `create_all()` alone
    never alters existing tables. Wired into main.py. Stand-in for Alembic.
  - Void button wired in Shell.jsx: RightPanel's `onDelete` prop was never
    passed by Shell, so the button never rendered. Now wired with native
    confirm + reason prompts.
  - Overpayments rejected: `validate_entry_invariants` now rejects
    `paid > balance_owed` when no discount is given (was silently accepted).
  - Server-side count endpoints: `GET /api/entries/count`,
    `/api/entries/missing-docs/count`, `/api/reports/creditors/count`.
    Sidebar uses these instead of fetching full lists every 60s.

  **End-to-end runtime test (all passed)**
  Tested the full void flow against running backend + frontend:
  - Recording a purchase works; entry appears in Ledger; counts update.
  - Soft-delete verified: voided a duplicate purchase — entry retained in DB,
    filtered from Ledger, VOID action with reason written to audit log
    (confirmed via `/api/entries/audit-log/all`).
  - Void button renders in RightPanel (PR fix confirmed working).
  - Recording a Return linked to a purchase works; negative total enforced;
    `linked_to` dropdown shows valid purchases only.
  - **Void-chain protection confirmed**: attempting to void a parent purchase
    while its linked return was still active was BLOCKED with a clear message
    naming the blocking entry. This is the Codex Critical fix, proven.
  - Full chain completed: voided the return first (succeeded), then the parent
    purchase (succeeded). Ledger correctly emptied, counts to 0.
  - SST label, bidirectional linked-entries panel, migration startup — all
    verified working.

  **Observations / minor follow-ups noted during testing**
  - A hung POST (e.g. backend down) leaves the Record button spinning forever
    with no timeout. Add an axios timeout + error toast.
  - Post-submit success feedback is weak — no toast — which caused a duplicate
    entry during testing (user resubmitted thinking it failed). Add a success
    toast.
  - Audit Log view is still a stub; the data is useful, worth building next.

- 2026-05-21 (session 7): Codex follow-up integrity fixes.

  **Accounting / contract fixes**
  These changes were made by Codex in this session after reviewing Claude's
  Session 6 handoff and the latest `origin/main`.
  - Purchase void now checks supplier-level payments as well as linked children.
    Because payments are not linked to individual purchases, the previous guard
    only blocked linked returns/credit notes. Now voiding a purchase is rejected
    if the supplier has active payments and removing the purchase would leave a
    negative supplier balance.
  - Return / credit note creation is capped against the linked purchase total,
    including existing non-voided returns against that purchase.
  - Missing-document filters and counts now treat NULL, empty string, and
    whitespace-only values as missing consistently.
  - `/api/reports/creditors/count` now matches the Creditors UI by counting only
    suppliers with visible non-zero balances.
  - `backend/mcp_serve.py` now reads `ACCOUNTING_API` from the environment, so
    docker-compose's `ACCOUNTING_API=http://backend:8000/api` works.
  - CORS now allows both `http://localhost:5173` and
    `http://127.0.0.1:5173`. Manual browser testing used `127.0.0.1`; the
    previous localhost-only allowlist caused every POST preflight to fail with
    `OPTIONS /api/entries/ 400`.

  **Verification**
  - Backend Python files compile with `python -m py_compile`.
  - Frontend production build passes with Vite.
  - Manual browser test passed for supplier-payment void guard: purchase
    `TXN-087942` with active payment `TXN-202805` was blocked with the expected
    negative-balance warning.
  - Codex also completed the first UX follow-up: axios now has a 15s default
    timeout, and RecordForm surfaces clearer validation, timeout, network, and
    success toasts instead of leaving the Record button spinning indefinitely.
    Manual browser tests confirmed both validation feedback and the
    backend-unreachable toast.
  - Follow-up fix: `Shell.jsx` no longer keys `RecordForm` by `refreshKey`.
    The old key caused the form to remount immediately after `onRecorded()`,
    wiping the success toast even though the entry was saved.
  - Codex started the idempotency-key TODO: `POST /api/entries/` now accepts an
    `Idempotency-Key` header, stores the key and payload fingerprint on the
    created entry, returns the original entry on exact replay, and rejects reuse
    of the same key with a different payload. RecordForm keeps one key per draft
    and rotates it after success/cancel/type change.
  - Codex redesigned the frontend interface as an accounting workstation:
    introduced `Shell.module.css`, widened the right detail rail, refreshed the
    sidebar, RecordForm, Ledger, Creditors, RightPanel, and HermesChatBar visual
    systems with a restrained neutral palette, tighter controls, clearer active
    states, and more consistent spacing. Behaviour is intended to remain
    unchanged.
  - Visible product name changed from MyAkaun/Hermes Accounting to
    **AccountMaxxer**. Hermes remains the agent/integration layer name in code
    and technical docs where relevant.
  - Redesign build passes with Vite; automated screenshot capture was attempted
    but Playwright is not available in the local Node runtime.
  - Attempted to install backend dependencies into a temporary Codex venv for
    runtime API checks, but this machine's active Python is 3.14 and
    `pydantic-core==2.18.2` has no usable wheel here; building from source
    failed because the MSVC linker (`link.exe`) is not installed. Runtime
    scenario tests still need to be run in the project's normal Python env.

- 2026-05-22 (session 8): Codex Decimal money pass.

  **Accounting precision**
  - Replaced SQLAlchemy `Float` money fields with `Numeric(..., asdecimal=True)`
    on `Entry` and `AuditLog`.
  - Replaced `EntryCreate` money/rate inputs with Pydantic `Decimal` fields.
  - Added `backend/money.py` for shared money quantization, rate quantization,
    and the half-cent tolerance used by validation/reporting.
  - Updated entry validation, supplier-balance checks, month-end reports,
    creditor reports, aged-payables summary, and Hermes context generation to do
    backend arithmetic with `Decimal` instead of binary floats.
  - API JSON remains frontend-compatible: FastAPI encodes Decimal values as JSON
    numbers, so React components can continue using `Number(...)`.

  **Verification**
  - Backend Decimal paths compile with `python -m py_compile`.
  - Disposable SQLite API smoke test passed: purchase + payment with settlement
    discount stored as `Decimal`, idempotency replay returned the same entry,
    creditor balance closed to 0, and month-end closing balance serialized as a
    JSON number.
  - Legacy SQLite compatibility smoke test passed: an old table with `FLOAT`
    columns was read through the new `Numeric` model as `Decimal`. Note that
    SQLite type affinity means this is an ORM/API precision fix, not a full
    physical table rebuild; a production-grade migration should still be done
    before moving to a stricter database.

- 2026-05-22 (session 9): Codex TODO sweep.

  **Security / audit**
  - Added optional bearer-token API auth. If `ACCOUNTMAXXER_API_TOKEN` (or
    `ACCOUNTING_API_TOKEN`) is unset, localhost/dev behaviour is unchanged. If
    set, `/api/*` requires `Authorization: Bearer <token>` while `/health`
    remains public.
  - Added `ACCOUNTMAXXER_API_USER` / `ACCOUNTING_API_USER` as the server-side
    audit actor. When auth is enabled, entry creation, voiding, and period
    lock/unlock ignore spoofable frontend actor fields and use this configured
    backend identity.
  - Frontend axios sends `VITE_ACCOUNTMAXXER_API_TOKEN` as a bearer token when
    present.
  - `mcp_serve.py` now binds to `127.0.0.1` by default (`MCP_HOST` /
    `MCP_PORT` override available) and forwards `ACCOUNTING_API_TOKEN` or
    `ACCOUNTMAXXER_API_TOKEN` to the backend.
  - SQLite startup migrations now install `audit_log_no_update` and
    `audit_log_no_delete` triggers. They abort direct `UPDATE`/`DELETE` against
    `audit_log` with `audit_log is append-only`.

  **Accounting / identifiers**
  - Creditor aged buckets now age outstanding purchase balances, not gross
    purchase history. Payments and discounts reduce oldest open purchases FIFO;
    returns reduce their linked purchase first, then FIFO if needed.
  - `generate_short_id()` now produces ULID-style sortable IDs with random
    entropy instead of using the last six digits of the millisecond timestamp.
  - `GET /api/periods/current` now uses Malaysia UTC+8 time via a fixed
    timezone, avoiding Windows `tzdata` dependency issues.
  - FX metadata fields landed: `rate_source` and `rate_locked_at` on `Entry`,
    startup migration columns, backend defaults for manual FX rates, and
    RightPanel display.

  **Verification**
  - Backend Python files compile with `python -m py_compile`.
  - Frontend production build passes with Vite.
  - Combined disposable SQLite smoke test passed: unauthenticated API blocked
    when token set, `/health` public, server-side actor used for entries, FX
    metadata stored, aged total matched creditor balance after payment + linked
    return, audit triggers blocked raw updates, and 2,000 generated short IDs
    were unique.
  - Live browser smoke test passed before commit: recorded FX purchase
    `TXN-01KS7DHSPPQZ0HCYQJCMSA74BP` for `Browser FX Supplier`, success toast
    appeared, Ledger showed the ULID-style ID, RightPanel showed `Rate source`
    and `Rate locked`, creditor report aged the RM 50 balance as current, and no
    browser console errors were present.
  - README refreshed by Codex to match the current AccountMaxxer name, optional
    auth env vars, Decimal money behaviour, MCP localhost defaults, FX metadata,
    audit-log triggers, and remaining roadmap.

## Codex review TODOs (remaining)

From the merged Claude + Codex review. Approximate priority.

**Done (sessions 6-9):** void-chain protection, supplier-payment void guard,
startup migrations, void button wired, overpayment rejection, return cap against
linked purchase total, server-side count endpoints, missing-doc consistency,
MCP `ACCOUNTING_API` env var, Decimal-backed backend money arithmetic, optional
bearer-token auth, MCP localhost binding, audit-log triggers, settlement-aware
aged buckets, ULID-style short IDs, Malaysia current-period timezone, FX
metadata, and repo .gitignore cleanup.

**Still remaining:**

1. **Reversing-entry pattern** as the long-term upgrade for void. The status
    column landed in v8 is the pragmatic version; the proper accounting pattern
    creates a counter-entry and flags both as voided. RightPanel copy has been
    updated to match current behaviour so the UI no longer lies about it.

**UX follow-ups (found during session 6 testing):** done in session 7.
