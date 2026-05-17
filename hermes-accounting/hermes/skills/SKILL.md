---
name: accounting-my
description: Malaysian SME accounting — purchases, credit notes, payments, month-end,
             audit trail, LHDN e-invoicing, and SST treatment
version: 1.0.0
metadata:
  hermes:
    tags: [malaysia, accounting, sst, lhdn, audit]
    category: accounting-my
---

# Malaysian Accounting Skill

## When to Use
Load this skill for any accounting task involving a Malaysian business:
recording purchases, processing credit notes, reconciling payments,
preparing month-end balances, or reviewing the audit trail.

## GL Code Reference
| Code | Category |
|------|----------|
| 2100 | Accounts Payable |
| 4200 | Discount Received (income — not a purchase reduction) |
| 5100 | Cost of Goods Sold |
| 5200 | Utilities |
| 5300 | Repairs & Maintenance |
| 5400 | Office Supplies |
| 5500 | Transport & Logistics |
| 5600 | Professional Fees |
| 5700 | Rental & Lease |
| 5800 | Other Expenses |

## Entry Types
- purchase: debit expense GL, credit accounts payable (2100)
- return: reverse of a purchase — negative amounts, link to original entry
- payment: debit accounts payable (2100), credit bank
  - if paid < balance owed → difference = discount received → GL 4200 (income)

## Settlement Discount Logic
When a supplier accepts less than the full balance:
  discount_received = balance_owed - amount_paid
  This is INCOME (GL 4200), not a reduction in purchase cost.
  Requires supplier written confirmation to be filed as supporting document.

## Foreign Currency Procedure
1. Record original currency, original amount, and exchange rate
2. MYR amount = original_amount × fx_rate (rounded to 2dp)
3. File bank's or money changer's rate confirmation as supporting document
4. Common pairs: INR→MYR (~0.04182), USD→MYR (~4.48), SGD→MYR (~3.35)

Note: Indian lakh notation — 1,00,000 = 100,000 (not 1 million)

## Audit Requirements
Every entry must have:
1. Date, supplier name, reference number (supplier's invoice/CN/cheque number)
2. GL category
3. Supporting document reference (scanned file path or storage key)
4. Recorded by (name or initials)
5. For credit notes: linked_to field pointing to original purchase TXN ID
6. For foreign currency: original amount, currency, and rate

## Month-End Checklist
Before locking a period:
- [ ] All entries have document references
- [ ] All entries have supplier reference numbers
- [ ] Credit notes linked to original purchases
- [ ] Supplier statements reconciled against ledger balances
- [ ] Bank statement reconciled
- [ ] SST input tax claimability reviewed
- [ ] Discount received (GL 4200) confirmed with supplier

## LHDN e-Invoice Quick Reference
Required fields: TIN, BRN (SSM-registered), MSIC code, document type code
Document type codes: 01=Invoice, 02=Credit Note, 03=Debit Note, 11=Self-billed Invoice
Self-billed requires written supplier consent on file.
Rejection: re-check BRN exact match, MSIC code, mandatory field completeness.

## Pitfalls
- Professional fees (GL 5600): usually subject to 8% service tax — verify supplier's SST registration
- "Other Expenses" (GL 5800): flag for reclassification to more specific GL where possible
- Indian lakh notation common in cross-border invoices from India
- Chinese receipts: 收据 = receipt (non-tax), 发票 = invoice (tax)
- Missing TIN on supplier invoice → cannot submit to MyInvois, must chase supplier
