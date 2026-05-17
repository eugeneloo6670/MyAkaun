# Hermes Accounting — Project Knowledge Base

## What This Is

A Malaysia-specific AI-powered accounting system built on top of the Hermes Agent
(github.com/nousresearch/hermes-agent). Scoped initially to:
- Recording purchases and receipts
- Credit notes / returns
- Payments to suppliers with settlement discount handling
- Month-end GL balances
- Full audit trail with kanban paper trail
- Period locking

## Competitive Context

### Tofu (gotofu.com)
- AI-powered accounts payable automation
- Extracts line items from invoices/receipts
- Integrates with Xero/QuickBooks
- 200+ language OCR support
- Starts at ~USD 79/month
- Weakness: narrow document extraction only — no reasoning, no memory, no autonomous action

### Access UBS Evo BSM (actiwise.com.my)
- Malaysia-specific property/strata management system
- Built-in LHDN e-invoicing compliance
- AI is a chatbot layer on top of structured data — not agent-driven
- Vertical-specific (property only)
- Weakness: static product, AI cannot act autonomously

### Our Differentiation
- Hermes agent with evolving skill memory — gets smarter per client over time
- MCP server exposes ledger as tools Hermes can act on autonomously
- WhatsApp/Telegram integration via Hermes gateway
- Nightly autonomous review via Hermes cron
- Malaysia-specific: LHDN e-invoicing, SST treatment, MPERS standards baked into skills
- Full audit trail with period locking — audit-ready from day one
- Foreign currency support with FX rate tracking (INR, USD, SGD, CNY, EUR → MYR)
- Multilingual document ingestion (BM, Chinese Simplified/Traditional, Tamil, English)
- Backend entirely in English for audit clarity; client comms auto-translated

## Currency Notes

Exchange rate used in demo: 1 INR = 0.04182 MYR (as of May 2026)
Indian lakh notation: 1,00,000 = 100,000

### Asia Trade Centre demo transactions
| # | Transaction | INR | MYR |
|---|---|---|---|
| 1 | Purchase | 1,00,000 | 4,182.00 |
| 2 | Return | 10,000 | 418.20 |
| 3 | Further purchase | 50,000 | 2,091.00 |
| — | Balance owed | 1,40,000 | 5,854.80 |
| 4 | Cheque paid | 1,35,000 | 5,647.70 |
| — | Discount received | 5,000 | 209.10 |

Discount received → GL 4200 (income), not a purchase reduction.

## Malaysian Regulatory Context

- LHDN e-Invoice (MyInvois): mandatory for businesses above RM 150k turnover
- SST rates: 6% or 8% service tax, 10% sales tax
- MPERS: Malaysian Private Entities Reporting Standard (for SMEs)
- CP204: Instalment tax estimation
- MSIC codes required on e-invoices
- BRN (Business Registration Number) must match SSM exactly

## GL Code Structure Used

| Code | Category |
|------|----------|
| 2100 | Accounts Payable |
| 4200 | Discount Received (income) |
| 5100 | Cost of Goods Sold |
| 5200 | Utilities |
| 5300 | Repairs & Maintenance |
| 5400 | Office Supplies |
| 5500 | Transport & Logistics |
| 5600 | Professional Fees |
| 5700 | Rental & Lease |
| 5800 | Other Expenses |

## Transaction ID Format
TXN-XXXXXX (last 6 digits of Unix timestamp)

## Audit Trail Design Principles
- audit_log table is append-only — no UPDATE or DELETE ever exposed via API
- Every CREATE and DELETE action is logged with timestamp, user, amount, doc ref
- Period lock/unlock events logged in amber in audit log
- Missing document references flagged red on kanban cards
- Linked transactions tracked bidirectionally (credit notes link to original purchase)
