"""Generate a realistic synthetic test pack for TAU's Data & Document Chat.

Produces:
  1. northvale_bank_statement_q3_2025.pdf  - 3 monthly statements, ruled tables
  2. vendor_master_2025.csv                - 35 vendors with amounts/TIN/W-9
  3. expense_policy_2025.pdf               - narrative policy, NO tables (pure RAG)
  4. ANSWER_KEY.md                         - ground truth computed from the data

All figures are computed from the same source data used to render, so the
answer key is exact by construction.
"""
import csv
import os
from collections import defaultdict

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

OUT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- source data
# (date, description, withdrawal, deposit)
MONTHS = {
    "July 2025": ("07", 24800.00, [
        ("07/01/2025", "Customer Deposit - Invoice 2101", 0, 8400.00),
        ("07/02/2025", "ACH Payment - Ironwood Timber Supply", 3250.00, 0),
        ("07/05/2025", "Check 2041 - Rivera Consulting LLC", 1450.00, 0),
        ("07/07/2025", "Debit Card - Fastenal #221", 385.20, 0),
        ("07/08/2025", "ACH Debit - Paychex Payroll", 9800.00, 0),
        ("07/10/2025", "Customer Deposit - Invoice 2107", 0, 6120.50),
        ("07/12/2025", "ACH Payment - Ironwood Timber Supply", 2100.00, 0),
        ("07/14/2025", "Debit Card - Shell Oil 4471", 142.85, 0),
        ("07/15/2025", "Wire Transfer - Summit Equipment Rental", 4200.00, 0),
        ("07/18/2025", "Check 2042 - Delgado Landscaping", 875.00, 0),
        ("07/21/2025", "Customer Deposit - Invoice 2115", 0, 5250.00),
        ("07/23/2025", "Debit Card - Uline Shipping", 268.40, 0),
        ("07/25/2025", "Monthly Service Fee", 35.00, 0),
        ("07/28/2025", "Transfer to Savings *9021", 3000.00, 0),
        ("07/30/2025", "Interest Credit", 0, 4.85),
    ]),
    "August 2025": ("08", None, [
        ("08/01/2025", "Customer Deposit - Invoice 2122", 0, 9350.00),
        ("08/04/2025", "ACH Payment - Ironwood Timber Supply", 1780.00, 0),
        ("08/06/2025", "Check 2043 - Rivera Consulting LLC", 2200.00, 0),
        ("08/08/2025", "ACH Debit - Paychex Payroll", 9800.00, 0),
        ("08/11/2025", "Debit Card - Grainger Industrial", 1620.75, 0),
        ("08/13/2025", "Customer Deposit - Invoice 2130", 0, 4875.00),
        ("08/15/2025", "Wire Transfer - Summit Equipment Rental", 3150.00, 0),
        ("08/18/2025", "Debit Card - Fastenal #221", 512.30, 0),
        ("08/20/2025", "Check 2044 - City of Brookfield Permit", 425.00, 0),
        ("08/22/2025", "ACH Payment - Cascade Fuel Co", 1340.60, 0),
        ("08/25/2025", "Monthly Service Fee", 35.00, 0),
        ("08/27/2025", "Customer Deposit - Invoice 2141", 0, 7200.00),
        ("08/29/2025", "Debit Card - Amazon Business", 318.95, 0),
        ("08/31/2025", "Interest Credit", 0, 5.12),
    ]),
    "September 2025": ("09", None, [
        ("09/02/2025", "Customer Deposit - Invoice 2150", 0, 11400.00),
        ("09/03/2025", "ACH Payment - Ironwood Timber Supply", 2960.00, 0),
        ("09/05/2025", "Check 2045 - Delgado Landscaping", 1150.00, 0),
        ("09/08/2025", "ACH Debit - Paychex Payroll", 10200.00, 0),
        ("09/10/2025", "Debit Card - Grainger Industrial", 845.60, 0),
        ("09/12/2025", "Wire Transfer - Summit Equipment Rental", 2875.00, 0),
        ("09/15/2025", "Customer Deposit - Invoice 2158", 0, 6480.00),
        ("09/17/2025", "Check 2046 - Rivera Consulting LLC", 1875.00, 0),
        ("09/19/2025", "Debit Card - Shell Oil 4471", 198.40, 0),
        ("09/22/2025", "ACH Payment - Cascade Fuel Co", 1105.25, 0),
        ("09/24/2025", "Debit Card - Uline Shipping", 442.10, 0),
        ("09/25/2025", "Monthly Service Fee", 35.00, 0),
        ("09/26/2025", "Transfer to Savings *9021", 4000.00, 0),
        ("09/29/2025", "Customer Deposit - Invoice 2166", 0, 5900.00),
        ("09/30/2025", "Interest Credit", 0, 6.03),
    ]),
}

VENDORS = [
    # name, tin, entity_type, w9_on_file, category, ytd_paid, state
    ("Ironwood Timber Supply", "84-2910477", "LLC", "Yes", "Materials", 10090.00, "OR"),
    ("Rivera Consulting LLC", "87-3320918", "LLC", "Yes", "Professional Services", 5525.00, "WA"),
    ("Summit Equipment Rental", "91-4471203", "Corporation", "Yes", "Equipment", 10225.00, "OR"),
    ("Delgado Landscaping", "", "Sole Proprietor", "No", "Subcontractor", 2025.00, "OR"),
    ("Paychex Payroll", "16-1124166", "Corporation", "Yes", "Payroll Service", 29800.00, "NY"),
    ("Grainger Industrial", "36-1150280", "Corporation", "Yes", "Supplies", 2466.35, "IL"),
    ("Fastenal Company", "41-0948415", "Corporation", "Yes", "Supplies", 897.50, "MN"),
    ("Cascade Fuel Co", "93-2288104", "LLC", "Yes", "Fuel", 2445.85, "WA"),
    ("Uline Shipping", "36-3184090", "Corporation", "Yes", "Supplies", 710.50, "WI"),
    ("Amazon Business", "91-1646860", "Corporation", "Yes", "Supplies", 318.95, "WA"),
    ("Shell Oil", "13-1712300", "Corporation", "Yes", "Fuel", 341.25, "TX"),
    ("City of Brookfield", "", "Government", "No", "Permits", 425.00, "OR"),
    ("Marisol Vega", "", "Individual", "No", "Subcontractor", 3200.00, "OR"),
    ("Thornton Legal Group", "45-7781920", "Partnership", "Yes", "Professional Services", 7400.00, "OR"),
    ("BlueRidge Accounting", "88-1029384", "LLC", "Yes", "Professional Services", 4800.00, "ID"),
    ("Harborline Freight", "20-4471882", "Corporation", "Yes", "Freight", 1875.40, "CA"),
    ("Kestrel Design Studio", "", "Sole Proprietor", "No", "Marketing", 2650.00, "OR"),
    ("Northvale Insurance", "23-9982017", "Corporation", "Yes", "Insurance", 6300.00, "OR"),
    ("Pinnacle IT Services", "47-3320019", "LLC", "Yes", "IT", 5120.00, "WA"),
    ("Grover Tree Care", "", "Sole Proprietor", "No", "Subcontractor", 1480.00, "OR"),
    ("Redstone Aggregates", "82-1177340", "Corporation", "Yes", "Materials", 8940.00, "OR"),
    ("Willamette Nursery LLC", "26-5590128", "LLC", "Yes", "Materials", 4210.00, "OR"),
    ("Tobias Mercer", "", "Individual", "No", "Subcontractor", 950.00, "WA"),
    ("Cobalt Print Shop", "31-8890021", "LLC", "Yes", "Marketing", 580.00, "OR"),
    ("Meridian Sanitation Services", "", "LLC", "No", "Waste", 1320.00, "OR"),
    ("Alder Creek Surveying", "56-1200983", "LLC", "Yes", "Professional Services", 3750.00, "OR"),
    ("Vantage Safety Supply", "77-2210094", "Corporation", "Yes", "Supplies", 1105.60, "UT"),
    ("Juniper Fleet Maintenance", "", "Sole Proprietor", "No", "Vehicle", 2890.00, "OR"),
    ("Stonebridge Rentals", "64-9987120", "Corporation", "Yes", "Equipment", 520.00, "OR"),
    ("Elena Fischer", "", "Individual", "No", "Professional Services", 4100.00, "OR"),
    ("Coastal Uniform Co", "39-1120876", "Corporation", "Yes", "Uniforms", 780.25, "WA"),
    ("Timberline Waste", "72-4408811", "LLC", "Yes", "Waste", 2140.00, "OR"),
    ("Orchard Hill Supply", "", "Sole Proprietor", "No", "Materials", 615.00, "OR"),
    ("Beacon Telecom", "13-3398201", "Corporation", "Yes", "Utilities", 3420.00, "NY"),
    ("Sable Ridge Fencing", "", "Sole Proprietor", "No", "Subcontractor", 5300.00, "OR"),
]
VENDOR_HEADER = ["vendor_name", "tin", "entity_type", "w9_on_file", "category", "ytd_paid", "state"]

POLICY_SECTIONS = [
    ("1. Purpose and Scope", [
        "This policy governs the reimbursement of business expenses incurred by employees and "
        "the engagement of outside vendors by Northvale Grounds Management LLC. It applies to "
        "all employees, officers, and contract personnel of the company, effective January 1, 2025.",
        "Expenses that fall outside this policy require written approval from the Controller "
        "before they are incurred. Retroactive approval is granted only in documented emergencies.",
    ]),
    ("2. Mileage and Travel", [
        "Personal vehicle use for company business is reimbursed at fifty-eight cents per mile "
        "for the 2025 calendar year. Mileage logs must record the date, origin, destination, "
        "business purpose, and odometer readings. Commuting between an employee's residence and "
        "their primary work location is not reimbursable.",
        "Air travel must be booked in economy class unless the scheduled flight time exceeds six "
        "hours, in which case premium economy is permitted with prior approval. Rental vehicles "
        "are limited to mid-size class or below.",
        "The standard per diem for meals and incidental expenses is sixty-eight dollars per full "
        "day of travel within the continental United States. Partial travel days are reimbursed "
        "at seventy-five percent of the full per diem rate. Receipts are not required for per "
        "diem, but a travel itinerary must be attached to the expense report.",
    ]),
    ("3. Receipts and Documentation", [
        "An itemized receipt is required for any single expense of seventy-five dollars or more. "
        "Credit card statements alone are not acceptable documentation because they do not show "
        "the items purchased.",
        "Expense reports must be submitted within thirty days of the expense being incurred. "
        "Reports submitted more than sixty days after the expense date will not be reimbursed "
        "except with Controller approval.",
    ]),
    ("4. Approval Thresholds", [
        "Expenditures up to one thousand dollars may be approved by a department supervisor. "
        "Expenditures between one thousand and ten thousand dollars require the approval of the "
        "Controller. Any commitment exceeding ten thousand dollars requires written approval "
        "from the Managing Member before the obligation is entered into.",
        "Splitting a single purchase into multiple smaller transactions in order to remain below "
        "an approval threshold is prohibited and is treated as a disciplinary matter.",
    ]),
    ("5. Vendor Engagement and Form 1099", [
        "Before any payment is issued, a new vendor must provide a completed Form W-9. The "
        "accounting department will not release payment to a vendor without a W-9 on file. "
        "Vendors organized as corporations are generally exempt from Form 1099-NEC reporting, "
        "with the notable exception of payments made to attorneys, which are reportable "
        "regardless of the law firm's entity type.",
        "The company issues Form 1099-NEC to each eligible non-corporate vendor that receives "
        "six hundred dollars or more in aggregate payments during the calendar year. Aggregation "
        "is performed across all accounts and all payment methods. Payments made by credit card "
        "or through a third-party settlement network are excluded, as those are reported by the "
        "processor on Form 1099-K.",
        "Vendor records are reviewed each January. Any vendor missing a taxpayer identification "
        "number at that time is subject to backup withholding at twenty-four percent until the "
        "documentation is received.",
    ]),
    ("6. Prohibited Expenses", [
        "The following are not reimbursable under any circumstance: personal entertainment, "
        "traffic and parking fines, personal grooming, in-flight purchases unrelated to business, "
        "and alcohol purchased outside of a documented client entertainment event.",
        "Client entertainment involving alcohol requires the attendance of at least one company "
        "officer and must list all attendees and the business purpose on the expense report.",
    ]),
]


def money(x):
    return f"{x:,.2f}"


def build_statement_pdf(path):
    doc = SimpleDocTemplate(path, pagesize=LETTER,
                            leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            title="Northvale Grounds Management - Bank Statements Q3 2025")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=14, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=ss["Normal"], fontSize=9, textColor=colors.HexColor("#444444"))
    story = []
    balance = 24800.00
    per_month = {}

    for idx, (month, (mm, _start, txns)) in enumerate(MONTHS.items()):
        opening = balance
        dep = sum(t[3] for t in txns)
        wd = sum(t[2] for t in txns)
        closing = round(opening + dep - wd, 2)
        per_month[month] = dict(opening=opening, deposits=round(dep, 2),
                                withdrawals=round(wd, 2), closing=closing, count=len(txns))

        story.append(Paragraph("Northvale Community Bank", h1))
        story.append(Paragraph("Business Checking Statement", sub))
        story.append(Paragraph("Account Holder: Northvale Grounds Management LLC", sub))
        story.append(Paragraph("Account Number: ****-****-9021", sub))
        story.append(Paragraph(f"Statement Period: {month}", sub))
        story.append(Spacer(1, 10))

        summary = [["Beginning Balance", f"${money(opening)}"],
                   ["Total Deposits & Credits", f"${money(dep)}"],
                   ["Total Withdrawals & Debits", f"${money(wd)}"],
                   ["Ending Balance", f"${money(closing)}"]]
        st = Table(summary, colWidths=[2.6 * inch, 1.4 * inch])
        st.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(st)
        story.append(Spacer(1, 12))

        rows = [["Date", "Description", "Withdrawals", "Deposits", "Balance"]]
        run = opening
        for d, desc, w, dp in txns:
            run = round(run - w + dp, 2)
            rows.append([d, desc,
                         money(w) if w else "",
                         money(dp) if dp else "",
                         money(run)])
        tt = Table(rows, colWidths=[0.85 * inch, 3.1 * inch, 1.05 * inch, 1.0 * inch, 1.05 * inch],
                   repeatRows=1)
        tt.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#AAAAAA")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3B63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(tt)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "This statement is a synthetic sample created for software testing. "
            "Any resemblance to a real bank, business, or person is coincidental.", sub))
        balance = closing
        if idx < len(MONTHS) - 1:
            story.append(PageBreak())

    doc.build(story)
    return per_month


def build_policy_pdf(path):
    doc = SimpleDocTemplate(path, pagesize=LETTER,
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch,
                            title="Northvale Grounds Management - Expense and Vendor Policy 2025")
    ss = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=ss["Heading1"], fontSize=15, spaceAfter=4)
    hd = ParagraphStyle("h", parent=ss["Heading2"], fontSize=11, spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=9.5, leading=14, spaceAfter=7)
    story = [Paragraph("Northvale Grounds Management LLC", title),
             Paragraph("Expense Reimbursement and Vendor Engagement Policy - 2025", body),
             Spacer(1, 6)]
    for heading, paras in POLICY_SECTIONS:
        story.append(Paragraph(heading, hd))
        for p in paras:
            story.append(Paragraph(p, body))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Synthetic document created for software testing only.", body))
    doc.build(story)


def build_vendor_csv(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(VENDOR_HEADER)
        for row in VENDORS:
            w.writerow(row)


def build_answer_key(path, per_month):
    tot_dep = round(sum(m["deposits"] for m in per_month.values()), 2)
    tot_wd = round(sum(m["withdrawals"] for m in per_month.values()), 2)
    tot_txn = sum(m["count"] for m in per_month.values())

    ytd = [v[5] for v in VENDORS]
    over600 = [v for v in VENDORS if v[5] >= 600]
    no_w9 = [v for v in VENDORS if v[3] == "No"]
    no_w9_over600 = [v for v in VENDORS if v[3] == "No" and v[5] >= 600]
    non_corp_over600 = [v for v in VENDORS if v[5] >= 600 and v[2] not in ("Corporation", "Government")]
    by_cat = defaultdict(float)
    for v in VENDORS:
        by_cat[v[4]] += v[5]
    top_cat = sorted(by_cat.items(), key=lambda kv: -kv[1])[:5]

    lines = [
        "# TAU Data & Document Chat - synthetic test pack ANSWER KEY",
        "",
        "Files: `northvale_bank_statement_q3_2025.pdf` (3 pages, ruled tables), "
        "`vendor_master_2025.csv` (35 rows), `expense_policy_2025.pdf` (narrative, NO tables).",
        "",
        "## A. Bank statement (PDF with tables -> should be answerable by SQL or RAG)",
        "",
        "| Question | Answer |",
        "|---|---|",
    ]
    for m, d in per_month.items():
        lines.append(f"| {m}: beginning balance | ${money(d['opening'])} |")
        lines.append(f"| {m}: total deposits | ${money(d['deposits'])} |")
        lines.append(f"| {m}: total withdrawals | ${money(d['withdrawals'])} |")
        lines.append(f"| {m}: ending balance | ${money(d['closing'])} |")
        lines.append(f"| {m}: transaction count | {d['count']} |")
    lines += [
        f"| Q3 total deposits (all 3 months) | ${money(tot_dep)} |",
        f"| Q3 total withdrawals (all 3 months) | ${money(tot_wd)} |",
        f"| Q3 total transaction rows | {tot_txn} |",
        f"| Largest single withdrawal | ${money(10200.00)} (09/08 Paychex Payroll) |",
        f"| Payroll paid across Q3 | ${money(9800 + 9800 + 10200)} |",
        f"| Ironwood Timber Supply paid across Q3 | ${money(3250 + 2100 + 1780 + 2960)} |",
        "",
        "## B. Vendor master CSV (SQL)",
        "",
        "| Question | Answer |",
        "|---|---|",
        f"| Number of vendors | {len(VENDORS)} |",
        f"| Total YTD paid (all vendors) | ${money(sum(ytd))} |",
        f"| Vendors paid >= $600 | {len(over600)} |",
        f"| Vendors with NO W-9 on file | {len(no_w9)} |",
        f"| Vendors with no W-9 AND >= $600 | {len(no_w9_over600)} |",
        f"| Non-corporate vendors >= $600 (1099-NEC candidates) | {len(non_corp_over600)} |",
        f"| Highest paid vendor | Paychex Payroll (${money(29800.00)}) |",
        f"| Vendors in Oregon (OR) | {len([v for v in VENDORS if v[6] == 'OR'])} |",
        f"| Number of distinct categories | {len(by_cat)} |",
        "",
        "Top categories by spend:",
        "",
        "| Category | Total |",
        "|---|---|",
    ]
    for c, amt in top_cat:
        lines.append(f"| {c} | ${money(amt)} |")
    lines += [
        "",
        "## C. Expense policy PDF (narrative, no tables -> pure RAG)",
        "",
        "| Question | Answer |",
        "|---|---|",
        "| Mileage reimbursement rate | 58 cents per mile (2025) |",
        "| Per diem (full day, CONUS) | $68 |",
        "| Partial travel day per diem | 75% of the full rate |",
        "| Receipt required at or above | $75 |",
        "| Expense report submission deadline | 30 days (hard stop 60 days) |",
        "| Supervisor approval limit | up to $1,000 |",
        "| Controller approval range | $1,000 - $10,000 |",
        "| Managing Member approval | over $10,000 |",
        "| 1099-NEC threshold | $600 aggregate |",
        "| Corporations exempt from 1099? | Generally yes, EXCEPT attorneys |",
        "| Backup withholding rate | 24% |",
        "| Economy class exception | flights over 6 hours -> premium economy w/ approval |",
        "",
        "## D. Cross-source questions (the hard ones)",
        "",
        "These need the right SOURCE chosen, which is what the routing fix targets:",
        "",
        "| Question | Correct source | Answer |",
        "|---|---|---|",
        f"| \"What were total deposits in Q3?\" | statement PDF | ${money(tot_dep)} |",
        f"| \"How many vendors do we have?\" | vendor CSV | {len(VENDORS)} |",
        "| \"What is the mileage rate?\" | policy PDF | 58 cents/mile |",
        f"| \"How many vendors are missing a W-9?\" | vendor CSV | {len(no_w9)} |",
        "| \"Do we send a 1099 to a corporation?\" | policy PDF | Generally no, except attorneys |",
        f"| \"How much did we pay Paychex this quarter?\" | statement PDF | ${money(29800.00)} |",
        "",
        "_Generated by make_testdata.py - all figures computed from the source data._",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    per_month = build_statement_pdf(os.path.join(OUT, "northvale_bank_statement_q3_2025.pdf"))
    build_policy_pdf(os.path.join(OUT, "expense_policy_2025.pdf"))
    build_vendor_csv(os.path.join(OUT, "vendor_master_2025.csv"))
    build_answer_key(os.path.join(OUT, "ANSWER_KEY.md"), per_month)
    print("built:")
    for f in sorted(os.listdir(OUT)):
        if not f.endswith(".py"):
            print("  ", f, os.path.getsize(os.path.join(OUT, f)), "bytes")
    for m, d in per_month.items():
        print(f"  {m}: open {d['opening']:>10,.2f}  dep {d['deposits']:>9,.2f}  "
              f"wd {d['withdrawals']:>10,.2f}  close {d['closing']:>10,.2f}  ({d['count']} txns)")
