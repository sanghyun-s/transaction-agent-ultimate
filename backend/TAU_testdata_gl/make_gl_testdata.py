"""Generate a realistic company-level GL with PLANTED review signals, plus an
answer key computed from the plants. Mirrors the approach that caught real bugs
in the CASSIA eval.

Planted signals (known ground truth):
  * round-number amounts (abs % 100 == 0)
  * weekend postings (Sat/Sun)
  * missing descriptions
  * new vendors (appear < 3 times)
  * near-approval-threshold amounts (95-100% of 5000/10000/25000)
  * a "teaching row" ~ just under transaction materiality that the override
    should restore to High
  * several "stacked" rows with >= 2 flags (fire the qualitative override)
"""
import csv
import os
import random
from datetime import date, timedelta

random.seed(42)
OUT = os.path.dirname(os.path.abspath(__file__))

START = date(2024, 1, 1)
END = date(2024, 12, 31)

# account_code, account_name, mean, sd
ACCOUNTS = [
    ("5000", "Office Supplies", 320, 120),
    ("5100", "Consulting Fees", 4200, 1500),
    ("5200", "Software Subscriptions", 900, 300),
    ("6000", "Salaries", 8500, 1200),
    ("6100", "Travel", 1100, 600),
    ("7000", "Equipment", 5200, 2200),
]
ESTABLISHED_VENDORS = [
    "Ironwood Supply", "Rivera Consulting", "CloudWorks Inc", "Payroll Partners",
    "Summit Travel", "Grainger Industrial", "BlueLine Software", "Metro Utilities",
]
ONEOFF_VENDORS = [
    "Wexler LLC", "Northgate Traders", "Apex Holdings", "Delco Services",
    "Vantage Group", "Orion Labs", "Crestline Co", "Halcyon Partners",
]


def business_date():
    while True:
        d = START + timedelta(days=random.randint(0, (END - START).days))
        if d.weekday() < 5:
            return d


def weekend_date():
    while True:
        d = START + timedelta(days=random.randint(0, (END - START).days))
        if d.weekday() >= 5:
            return d


def make_rows():
    rows = []
    jr = 1000

    # ---- baseline population (clean) ----
    for _ in range(430):
        code, name, mean, sd = random.choice(ACCOUNTS)
        amt = round(max(20, random.gauss(mean, sd)), 2)
        # avoid accidental round numbers in baseline
        if amt % 100 == 0:
            amt += round(random.uniform(0.13, 7.77), 2)
        vendor = random.choice(ESTABLISHED_VENDORS)
        rows.append({
            "date": business_date().isoformat(), "amount": amt,
            "account_code": code, "account_name": name, "vendor": vendor,
            "description": f"{name} payment to {vendor}", "journal_ref": f"JE{jr}",
            "_planted": "",
        })
        jr += 1

    planted = {"round": 0, "weekend": 0, "missing_desc": 0, "new_vendor": 0,
               "near_threshold": 0, "stacked_override": 0, "teaching": 0}

    # ---- single-signal plants ----
    for _ in range(8):  # round numbers
        code, name, *_ = random.choice(ACCOUNTS)
        rows.append({"date": business_date().isoformat(), "amount": random.choice([1000, 2000, 3000, 500]),
                     "account_code": code, "account_name": name,
                     "vendor": random.choice(ESTABLISHED_VENDORS),
                     "description": f"{name} round payment", "journal_ref": f"JE{jr}", "_planted": "round"})
        jr += 1; planted["round"] += 1

    for _ in range(6):  # weekend postings (non-round)
        code, name, mean, sd = random.choice(ACCOUNTS)
        amt = round(max(50, random.gauss(mean, sd)) + 0.55, 2)
        rows.append({"date": weekend_date().isoformat(), "amount": amt,
                     "account_code": code, "account_name": name,
                     "vendor": random.choice(ESTABLISHED_VENDORS),
                     "description": f"{name} weekend entry", "journal_ref": f"JE{jr}", "_planted": "weekend"})
        jr += 1; planted["weekend"] += 1

    for _ in range(6):  # missing description
        code, name, mean, sd = random.choice(ACCOUNTS)
        amt = round(max(50, random.gauss(mean, sd)) + 0.33, 2)
        rows.append({"date": business_date().isoformat(), "amount": amt,
                     "account_code": code, "account_name": name,
                     "vendor": random.choice(ESTABLISHED_VENDORS),
                     "description": "", "journal_ref": f"JE{jr}", "_planted": "missing_desc"})
        jr += 1; planted["missing_desc"] += 1

    for i in range(6):  # new vendors (each appears once)
        code, name, mean, sd = random.choice(ACCOUNTS)
        amt = round(max(50, random.gauss(mean, sd)) + 0.71, 2)
        rows.append({"date": business_date().isoformat(), "amount": amt,
                     "account_code": code, "account_name": name,
                     "vendor": ONEOFF_VENDORS[i],
                     "description": f"{name} one-off", "journal_ref": f"JE{jr}", "_planted": "new_vendor"})
        jr += 1; planted["new_vendor"] += 1

    for _ in range(5):  # near approval threshold (95-100% of 5000)
        rows.append({"date": business_date().isoformat(), "amount": round(random.uniform(4750, 4990), 2),
                     "account_code": "5100", "account_name": "Consulting Fees",
                     "vendor": random.choice(ESTABLISHED_VENDORS),
                     "description": "Consulting near-limit", "journal_ref": f"JE{jr}", "_planted": "near_threshold"})
        jr += 1; planted["near_threshold"] += 1

    # ---- stacked plants (>=2 flags → qualitative override → High) ----
    stacked_specs = [
        (4850.00, "Apex Holdings"),   # near-threshold + new vendor + weekend + blank desc
        (9850.00, "Wexler LLC"),      # near-threshold(10k) + new vendor + weekend
        (24850.00, "Orion Labs"),     # near-threshold(25k) + new vendor + missing desc
    ]
    for amt, vendor in stacked_specs:
        rows.append({"date": weekend_date().isoformat(), "amount": amt,
                     "account_code": "7000", "account_name": "Equipment",
                     "vendor": vendor, "description": "", "journal_ref": f"JE{jr}",
                     "_planted": "stacked_override"})
        jr += 1; planted["stacked_override"] += 1

    # ---- the teaching row: ~just under txn materiality, stacked → override restores High ----
    rows.append({"date": weekend_date().isoformat(), "amount": 4790.30,
                 "account_code": "5100", "account_name": "Consulting Fees",
                 "vendor": "Crestline Co", "description": "", "journal_ref": f"JE{jr}",
                 "_planted": "teaching"})
    jr += 1; planted["teaching"] += 1

    random.shuffle(rows)
    return rows, planted


def main():
    rows, planted = make_rows()
    fields = ["date", "amount", "account_code", "account_name", "vendor", "description", "journal_ref"]
    path = os.path.join(OUT, "sample_gl_2024.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fields})

    # answer key
    n = len(rows)
    n_round = sum(1 for r in rows if abs(r["amount"]) % 100 == 0)
    n_missing = sum(1 for r in rows if not str(r["description"]).strip())
    key = [
        "# GL Audit Review Packet — sample_gl_2024.csv ANSWER KEY",
        "",
        f"Total rows: {n}",
        "",
        "## Planted signals (ground truth)",
        "",
        "| Signal | Count planted |",
        "|---|---|",
        f"| Round-number amounts | {planted['round']} (+ any incidental) |",
        f"| Weekend postings | {planted['weekend']} (+ stacked + teaching) |",
        f"| Missing descriptions | {planted['missing_desc']} (+ stacked + teaching) |",
        f"| New vendors (< 3 appearances) | {planted['new_vendor']} one-offs + stacked vendors |",
        f"| Near approval threshold | {planted['near_threshold']} (+ 3 stacked) |",
        f"| Stacked (>= 2 flags → override → High) | {planted['stacked_override']} |",
        f"| Teaching row ($4,790.30, stacked, override → High) | {planted['teaching']} |",
        "",
        "## Derived checks",
        "",
        f"- Rows with amount %% 100 == 0 (is_round_number): {n_round}",
        f"- Rows with blank description (missing_description): {n_missing}",
        "- The three stacked rows ($4,850 / $9,850 / $24,850) and the teaching row",
        "  ($4,790.30) each carry >= 2 discrete flags, so fraud_risk_flag = 1 and the",
        "  qualitative override should escalate them to High regardless of materiality.",
        "",
        "## Materiality (Private company, benchmark $150,000)",
        "",
        "- FS materiality: $6,000 (4%)",
        "- Performance materiality: $3,000 (50%)",
        "- Transaction materiality: $4,800 (80%)",
        "- The teaching row $4,790.30 is just under $4,800 transaction materiality,",
        "  so materiality alone would downgrade it — the override restores it to High.",
    ]
    with open(os.path.join(OUT, "ANSWER_KEY_GL.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(key))

    print(f"built sample_gl_2024.csv: {n} rows")
    print("planted:", planted)
    print(f"round-number rows: {n_round} | blank-desc rows: {n_missing}")


if __name__ == "__main__":
    main()
