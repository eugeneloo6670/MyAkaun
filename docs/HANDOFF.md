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

### v5 — Desktop shell UI
- Three-column layout: left nav (180px) | main content | right detail panel (240–280px)
- Right panel shows full entry detail on click:
  - Document status alert (red if missing)
  - All fields including FX details
  - Transaction linkage chips
  - Audit trail timeline
  - Recorded-by avatar
- Hermes chat bar at bottom of main panel (persistent)
- Live streaming response from Hermes agent

### v6 (current) — Frontend component build-out
Built as proper modular React components matching v5 spec. All use plain CSS
modules with consistent design tokens (cool neutrals, teal accent, amber for
warnings, red for missing docs / overdue).

**Files added under `frontend/src/components/`:**

- **RecordForm/** — entry form, four type buttons (Purchase / Credit Note / Return / Payment)
  - Supplier autocomplete with last-GL + last-currency memory
  - Period lock detection on date change → disables form
  - Linked-TXN dropdown for Credit Note / Return → auto-fills GL + SST + FX
  - FX block: original amount + currency + rate → live MYR calc
  - Payment type: live balance fetch + auto settlement discount → GL 4200
  - Overpayment warning when amount_paid > balance
  - Doc ref enforced when settlement discount applies
  - Strict validation, inline error messages, success/error toast
  - Calls `onRecorded(entry)` prop on success for parent refresh

- **Sidebar/** — 180px left rail
  - 4 nav sections: Entry, Ledger, Period, Audit
  - Live counts polled every 60s: entries, creditors, missing docs (red badge)
  - Current period chip at footer (month + open/locked status)
  - User avatar + role at bottom
  - Calls `onNavigate(viewId)` prop

- **Ledger/** — entry table with filters
  - Filters: free-text search, type, GL code, date range, doc status
  - Metrics row: entries shown, total debit, total credit, missing docs
  - Sortable columns, pagination (50/page)
  - CSV export client-side
  - Row click → calls `onSelectEntry(entry)` for RightPanel
  - Visual badges per entry type, red amount for negatives, FX line under amount

- **Creditors/** — AP aging report
  - Total payable + four bucket cards (0–30 / 31–60 / 61–90 / 90+ d)
  - Overdue buckets (61–90, 90+) styled red
  - Sort: balance desc/asc, supplier name, oldest first
  - Click row → expand drawer showing last 10 entries for that supplier
  - "Pay" button on each row → calls `onSelectSupplier({supplier, balance, action: 'pay'})`
    Parent should switch view to RecordForm with payment type pre-selected
  - Red left border on rows with 61+ day balances

- **RightPanel/** — 280px right rail (widened from 240px for FX detail readability)
  - Empty state when no entry selected
  - TXN-ID chip + entry type heading
  - Red doc-missing alert at top
  - Large amount display + FX breakdown
  - Field list: date, supplier, ref, GL, SST, method, discount, doc, recorded by
  - Linked transactions section (chips with TXN, type, amount)
  - Audit timeline with colored dots (CREATE=teal, DELETE=red, LOCK=amber)
  - "Void entry" action button at footer (creates reversing entry, original retained)

## Architecture

### Backend (FastAPI + Python) — unchanged
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
- Shell.jsx — three-column layout, view routing (still needs to be wired to new components — see "Integration TODO" below)
- HermesChatBar.jsx — streaming chat with Hermes agent
- api/client.js — axios wrapper
- components/RecordForm/ — v6 (new)
- components/Sidebar/ — v6 (new)
- components/Ledger/ — v6 (new)
- components/Creditors/ — v6 (new)
- components/RightPanel/ — v6 (new)

### Hermes Integration (3 levels) — unchanged
1. Chat bar → /api/hermes/query → hermes_bridge → streams response
2. MCP server (port 8001) → Hermes calls record_entry, query_ledger etc autonomously
3. Cron: nightly-accounting-review skill at 23:00 → WhatsApp summary

## Backend API contract assumed by v6 frontend

The new components assume these endpoints exist. If any are missing or
have a different shape, only the data-fetching `useEffect`s in each component
need touching — form/render logic is isolated.

### Entries
- `GET  /api/entries` — query: `type, gl_code, supplier, date_from, date_to, doc_status, search, limit, offset`. Returns `[entries]` or `{entries, total}`.
- `GET  /api/entries/count` → `{count: N}`
- `GET  /api/entries/suppliers` → `[{name, last_gl, last_currency}]`
- `GET  /api/entries/missing-docs/count` → `{count: N}`
- `GET  /api/entries/{txn_id}/audit-log` → `[{id, action, timestamp, user, note}]`
- `GET  /api/entries/{txn_id}/linked` → `[{txn_id, type, amount_myr}]`
- `POST /api/entries` — body shape varies by type, see RecordForm `buildPayload()`. Returns `{txn_id, ...}`.

### Reports
- `GET  /api/reports/creditors` → `[{supplier, balance, aging_0_30, aging_31_60, aging_61_90, aging_90_plus, last_activity}]`
- `GET  /api/reports/creditors/count` → `{count: N}`
- `GET  /api/reports/creditors?supplier=X` → single supplier balance (also works for the "current balance" widget in payment entry)

### Periods
- `GET  /api/periods/current` → `{month: "2026-05", locked: boolean}`
- `GET  /api/periods/{YYYY-MM}` → `{locked: boolean}`

## Integration TODO (next session, ~30 min)

Shell.jsx needs to wire the new components. Suggested structure:

```jsx
import Sidebar     from './components/Sidebar';
import RecordForm  from './components/RecordForm';
import Ledger      from './components/Ledger';
import Creditors   from './components/Creditors';
import RightPanel  from './components/RightPanel';
import HermesChatBar from './HermesChatBar';

export default function Shell() {
  const [view, setView] = useState('record');
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [paymentContext, setPaymentContext] = useState(null);

  const bump = () => setRefreshTick(t => t + 1);

  return (
    <div className="shell">
      <Sidebar activeView={view} onNavigate={setView} refreshTrigger={refreshTick} />
      <main className="main">
        {view === 'record'    && <RecordForm onRecorded={bump} prefill={paymentContext} />}
        {view === 'ledger'    && <Ledger onSelectEntry={setSelectedEntry} refreshTrigger={refreshTick} />}
        {view === 'creditors' && <Creditors
                                    onSelectSupplier={(ctx) => { setPaymentContext(ctx); setView('record'); }}
                                    onSelectEntry={setSelectedEntry}
                                    refreshTrigger={refreshTick}
                                  />}
        <HermesChatBar />
      </main>
      <RightPanel entry={selectedEntry} onClose={() => setSelectedEntry(null)} />
    </div>
  );
}
```

Note: `RecordForm` does NOT currently accept a `prefill` prop. To support
the "Pay supplier" flow from Creditors, add a `prefill` prop that pre-selects
type=payment and pre-fills supplier. ~10 lines.

## Key Business Logic — unchanged

### Settlement Discount
When supplier accepts less than full balance:
  discount_received = balance_owed - amount_paid
  → GL 4200 (income), NOT a reduction in purchase cost
  Requires supplier written confirmation as supporting document.

### Credit Note vs Return
Kept as separate buttons per user decision. Functionally identical
(both negative-amount entries linked to original). Distinction is for
audit clarity:
- Return = goods physically sent back (supplier issues CN as evidence)
- Credit Note = balance reduction without goods movement (price, rebate, damage)

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

## What Needs Building Next (priority order)

### High priority
- [ ] Shell.jsx — wire all v6 components (Integration TODO above)
- [ ] RecordForm `prefill` prop — accept `{supplier, balance, action}` for Creditors → Pay flow
- [ ] Backend endpoints check — verify the contract above matches reality, fix any mismatches
- [ ] KanbanTrail.jsx — paper-trail kanban (Purchases | CN | Payments | Discounts columns)

### Medium priority
- [ ] MonthEnd.jsx — GL breakdown per period, wired to `/api/reports/month-end/{month}`
- [ ] AuditLog.jsx — append-only log view, amber for period events, CSV export
- [ ] Periods.jsx — lock/unlock UI with confirmation modal

### Lower priority / future workstreams
- [ ] Document upload — base64 image storage OR S3 presigned URLs; OCR via Hermes
- [ ] Maker/checker approval workflow — adds `status` column (draft → pending_approval → posted → voided) + second user role
- [ ] LHDN e-invoice skill — `hermes/skills/lhdn-einvoicing/SKILL.md`
- [ ] SST treatment skill — `hermes/skills/sst-treatment/SKILL.md`
- [ ] PDF audit report generation
- [ ] AR module (separate session): sales invoices, customer receipts, debtors, GL 1200/4100/4300
- [ ] Multi-tenant support (per-company database separation)
- [ ] AI-powered chart of accounts customization per client

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

Consistent CSS variables across all v6 components:

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

Typography: native system stack (-apple-system, Segoe UI, etc).
Numeric columns: `font-variant-numeric: tabular-nums`.
Code/IDs: `"SF Mono", Menlo, Consolas, monospace`.

Avoid: gradients, decorative shadows, color animations, custom fonts.
This is an audit tool — restraint signals trustworthiness.

## Session Log

- 2026-05-17 (session 1): RecordForm.jsx + module.css built. Backend assumed complete per v5.
- 2026-05-18 (session 2): Sidebar, Ledger, Creditors, RightPanel all built. HANDOFF.md updated. Files staged in `/mnt/user-data/outputs/frontend/src/components/` for upload to GitHub repo.
