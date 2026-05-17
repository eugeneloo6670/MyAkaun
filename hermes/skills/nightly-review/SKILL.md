---
name: nightly-accounting-review
description: Runs every night — checks missing documents, overdue payables,
             and open period flags. Sends WhatsApp summary.
version: 1.0.0
metadata:
  hermes:
    tags: [accounting, automation, cron, malaysia]
    category: accounting-my
---

# Nightly Accounting Review

## Schedule
Add to Hermes cron: hermes cron add "0 23 * * *" /nightly-accounting-review

## Procedure

### Step 1 — Missing documents
Call tool: query_ledger with missing_docs=true
Count entries without document references.

### Step 2 — Overdue payables
Call tool: get_aged_payables
Extract suppliers with balances in 60d+ and 90d+ buckets.

### Step 3 — Open period status
Call tool: get_month_end_summary for current month (YYYY-MM).
Check missing_docs count and closing_balance.

### Step 4 — Compose summary
Write a plain-English summary. Format:

  Hermes Accounting — Nightly Review [DATE]
  ─────────────────────────────────────────
  Missing documents: [n] entries need supporting docs filed
    [list TXN IDs]

  Overdue payables:
    60–90 days: MYR [amount] — [suppliers]
    90+ days:   MYR [amount] — [suppliers]

  Period [YYYY-MM]: [open / ready to lock / locked]
    [any flags]

  Actions required:
    1. [action]
    2. [action]

### Step 5 — Deliver
Send summary via WhatsApp gateway to configured number.
Post summary to: POST /api/hermes/nightly-log

### Step 6 — Memory
Save a one-line note to memory:
  "Nightly review [date]: [n] missing docs, MYR [overdue] overdue payables"

## Pitfalls
- If API is unreachable, note the failure and retry once after 5 minutes
- Do not send if there are zero issues — only alert when action is needed
- Never include raw database IDs in the WhatsApp message — use short IDs (TXN-XXXXXX)
