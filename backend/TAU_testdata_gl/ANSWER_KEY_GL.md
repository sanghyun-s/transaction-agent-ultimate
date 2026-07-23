# GL Audit Review Packet — sample_gl_2024.csv ANSWER KEY

Total rows: 465

## Planted signals (ground truth)

| Signal | Count planted |
|---|---|
| Round-number amounts | 8 (+ any incidental) |
| Weekend postings | 6 (+ stacked + teaching) |
| Missing descriptions | 6 (+ stacked + teaching) |
| New vendors (< 3 appearances) | 6 one-offs + stacked vendors |
| Near approval threshold | 5 (+ 3 stacked) |
| Stacked (>= 2 flags → override → High) | 3 |
| Teaching row ($4,790.30, stacked, override → High) | 1 |

## Derived checks

- Rows with amount %% 100 == 0 (is_round_number): 8
- Rows with blank description (missing_description): 10
- The three stacked rows ($4,850 / $9,850 / $24,850) and the teaching row
  ($4,790.30) each carry >= 2 discrete flags, so fraud_risk_flag = 1 and the
  qualitative override should escalate them to High regardless of materiality.

## Materiality (Private company, benchmark $150,000)

- FS materiality: $6,000 (4%)
- Performance materiality: $3,000 (50%)
- Transaction materiality: $4,800 (80%)
- The teaching row $4,790.30 is just under $4,800 transaction materiality,
  so materiality alone would downgrade it — the override restores it to High.