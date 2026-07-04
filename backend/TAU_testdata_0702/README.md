# TAU synthetic test data (2026-07-02)

Fictional data for testing TAU. No real bank, business, or person is involved.
Company throughout: **Brightleaf Landscaping LLC**, period **June 2025**.

Each file targets specific TAU tools, and the "answer key" below lets you verify
the PDF service (and the existing tools) are classifying correctly.

--------------------------------------------------------------------
sample_bank_statement.pdf      → 1099 Worksheet · File Analyzer · PDF service
--------------------------------------------------------------------
Multi-column layout (Withdrawals / Deposits / Balance) — the layout that trips up
naive parsers. 12 transactions.

ANSWER KEY — vendor payments that SHOULD be included for 1099:
  Greenleaf Nursery ............ 2,490.00   (1,850.00 + 640.00 — TWO spellings,
                                             "Greenleaf Nursery" + "Greenleaf Nursery LLC",
                                             must aggregate to one vendor)   [> $600]
  Maria Sanchez ................   900.00                                     [> $600]
  Home Depot ...................   412.37
  Shell Oil ....................    78.50
  City of Portland .............   150.00   (business license — GOVERNMENT payee;
                                             a correct classifier flags this for review /
                                             likely 1099-exempt)
  Included vendor total ........ 4,030.87 ;  vendors over $600 = 2 (Greenleaf, Sanchez)

SHOULD be EXCLUDED (and why):
  ADP Payroll ....... 6,500.00  payroll
  Transfer to Savings 2,000.00  transfer
  Monthly Service Fee    25.00  bank fee
  Customer Deposits   7,950.00  income (deposits, not payments)
  Interest Credit         2.15  interest

RECONCILIATION SNAPSHOT (Source-A check):
  Beginning 12,450.00 + Deposits 7,952.15 − Withdrawals 12,555.87 = Ending 7,846.28  ✓
  (All four figures are printed on the statement.)

--------------------------------------------------------------------
sample_creditcard_statement.pdf → 1099 Worksheet · PDF service
--------------------------------------------------------------------
Single amount column with +/- signs. Tests a different layout family.

Included purchases:  Uline 318.44 · Fastenal 542.10 · Grainger 1,204.75 ·
                     Amazon 96.32 · United Rentals 875.00  → total 3,036.61
                     (over $600: Grainger, United Rentals)
Excluded:            Payment −1,240.00 (credit) · Interest Charge 18.90

--------------------------------------------------------------------
sample_gl.csv                  → File Analyzer · (future) GL Audit
--------------------------------------------------------------------
15 rows, QuickBooks-style columns (Date, Type, Num, Name, Memo, Account, Amount).
Deliberate test hooks:
  • Outlier:  "Pacific Equipment Co"  −45,000.00  (should trip anomaly detection)
  • Duplicate vendor spelling: "Greenleaf Nursery" vs "Greenleaf Nursery, LLC"
    (should trip File Analyzer's duplicate-vendor check)

--------------------------------------------------------------------
sample_vendors.csv             → 1099 Worksheet (optional "Known Vendor List")
--------------------------------------------------------------------
6 known vendors with placeholder entity types + masked TINs.

--------------------------------------------------------------------
sample_gl.xlsx                 → File Analyzer · xlsx path
--------------------------------------------------------------------
8 expense rows + a live =SUM() total.  Total = −5,002.19  (recalculated, 0 errors).
TINs are placeholders (XX-XXX####) — safe to commit.
