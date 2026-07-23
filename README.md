# 📊 Transaction Agent Ultimate (TAU)

**An AI-powered accounting utility hub** — a **FastAPI backend** and **Next.js frontend** that brings journal-entry generation, terminology help, file analysis, statement review, cross-statement consolidation, conversational data & document Q&A, GL audit-review triage, and an end-to-end 1099 workflow together in one bilingual (Korean / English) interface.

TAU is designed to **converge a family of accounting tools into a single hub.** Rather than shipping separate apps, each capability is folded in as a compact, function-named **add-on** that sits on a shared spine — one unified work archive, one PDF ingestion engine, one language setting. Standalone prototypes (PREPARE, CASSIA, LUCENT) are being reduced to add-ons and brought in one at a time.

> **Version 0.10.0** — adds the LUCENT add-on, **GL Audit Review Packet**: upload a company-level general-ledger export and get back a prioritized review queue, data-quality checks, and a three-block evidence memo per flagged row, each grounded in the audit standard the signal was designed around. This completes the convergence roadmap — all four planned add-ons (two PREPARE, one CASSIA, one LUCENT) are now in the hub.

---

## 🧱 The shared spine

Every tool reads from and writes to a small set of shared services. This is what keeps the hub cohesive as add-ons are added:

- **Work History** — a single SQLite-backed archive (`backend/tau_history.db`). Any tool can save a result; the Work History page lists everything across all tools, filters by tool, reopens a saved result, re-downloads it, or clears the archive.
- **PDF ingestion service** — one engine that turns a statement PDF into classified transactions plus two deterministic data-quality checks:
  - **Source A — reconciliation:** does the statement's own stated math balance? (`beginning + deposits − withdrawals − checks − transfers − fees = ending`)
  - **Source B — extraction completeness:** do the *extracted rows* sum back to the statement's stated activity totals? Catches missed or miscounted rows.

  Two backends: the **Claude PDF Skill** (accurate, column-aware) and a **rule engine** (instant, free). Both checks are computed once in the service and consumed by every statement-oriented tool.
- **Bilingual output** — a global language selector (Korean / English / Bilingual) with a per-tool override. Korean follows K-IFRS phrasing, English follows IFRS.

---

## 🎯 Tools

### Live today

#### 1. 📊 Journal Entry Generator
Describe a transaction in Korean or English (e.g. `사무용품 100,000원을 현금으로 구매`) and get a complete debit/credit entry, recommended account titles with plain-language notes, and a step-by-step principle breakdown. Save any result to Work History.

#### 2. 📖 Term Explainer
Enter an accounting term (e.g. `감가상각`, `accrual basis`) for a side-by-side bilingual explanation, a worked journal-entry example, and practical usage tips.

#### 3. 📋 Work History
The unified archive described above — no longer journal-only or session-only. Every tool's saved output lands here with a tool badge and timestamp, persists across navigation, and is re-openable and re-downloadable.

#### 4. 📁 File Analyzer
Upload CSV, Excel (`.xlsx`), or PDF. Cleans QuickBooks-style GL exports, flags outliers (Z-score), catches duplicate/variant vendor names, extracts PDF tables via pdfplumber, and produces a GPT-written summary with recommended actions.

#### 5. 📑 1099 Worksheet
Upload a bank/credit-card statement (PDF) plus an optional vendor master (CSV). Extracts and normalizes vendors, aggregates by canonical name, flags vendors crossing the $600 threshold, and generates a multi-sheet accountant-grade Excel workbook. Two modes: a deterministic **rule-based** pipeline (free) and a **Claude Agent** mode that orchestrates the tools and adds a plain-English summary.

#### 6. 📄 Statement Review — *first PREPARE add-on*
Upload one statement and get a per-statement bookkeeping review:
- **Row-level classification** — every transaction labeled (vendor payment, check, deposit, payroll, transfer, fee, interest), each marked included / excluded for 1099 aggregation with an exclusion reason.
- **Source A — reconciliation** — the statement's own stated figures laid out deterministically: `beginning + deposits − withdrawals − checks − transfers − fees = calculated ending`, compared against the reported ending, with a **Balanced / Off** verdict. Built on the "transcribe, don't compute" principle: the model transcribes the stated balances, and the arithmetic runs in one place on the backend.
- **Source B — extraction check** — a low-key indicator confirming the extracted rows sum back to the statement's stated activity totals (or flagging a possible gap). Handles both broken-out statements and statements that lump all debits into a single total.
- **Two modes** — *Quick preview* (rule engine, instant, free) and *Full analysis* (Claude PDF Skill, column-aware, ~1–4 min).
- Saves a clean markdown artifact to Work History.

#### 7. 📘 Consolidated Workbook — *second PREPARE add-on*
The vendor-level, cross-statement view. Upload **multiple** statements (plus an optional vendor master CSV) and get a single accountant-ready master workbook (Excel):
- **Cross-statement vendor aggregation** — the same vendor across statements is normalized to one canonical name and rolled up (e.g. two Greenleaf payments on different statements merge into one $2,490 vendor), so the same payee isn't split by statement-noise prefixes like `ACH Payment –` or `Check 1022 –`.
- **1099 eligibility** — flags vendors crossing the **$600 combined** threshold, with conservative **1099-NEC / REVIEW / EXEMPT** calls (a business with no entity suffix and no W-9 is flagged for review rather than silently asserted).
- **Deterministic cross-statement validation** — cross-statement vendor matches, combined-total threshold crossings, name variants, amount mismatches, and near-threshold vendors.
- **5-sheet master workbook** — Executive Summary (with Source-A reconciliation and Source-B extraction roll-ups), Master Vendor Summary, Validation Report, All Transactions, Per-Agent Summary.
- Lean by design: the on-screen surface is upload → build → one status line → **Download workbook**. All detail lives in the workbook. Default engine is the Skill; the rule engine is offered as a rough, free quick preview.

#### 8. 💬 Data & Document Chat — *first CASSIA add-on*
A chat-first assistant. The thread and composer are always available; **upload is a side action**, not a gateway. Each question routes automatically, based on what's loaded rather than on keywords:
- **General** — with nothing loaded, answers general accounting/tax questions directly.
- **SQL** — a CSV/Excel loads into an in-memory SQLite table; the model writes a **read-only** `SELECT`, it runs, and the result is explained (e.g. "how many vendors are missing a W-9?" → 11).
- **RAG** — a PDF is chunked, embedded, and retrieved via **in-memory cosine top-k**, then answered from the document (e.g. "what is the mileage reimbursement rate?" → 58¢/mile).

Routing is **schema-aware, not keyword-based**: with both a table and a document loaded, the model tries SQL and — if the schema genuinely can't answer — reports back so the question falls through to RAG. Because the decision comes from reading the schema rather than matching words, it works the same in Korean and English with no per-language keyword list. Explicit intent ("read the PDF" / "표에서") overrides.

A PDF is ingested two ways at once: as text chunks for RAG **and**, when it contains ruled tables, as rows in the same SQLite database — so a statement's figures can be answered exactly by SQL (e.g. "total deposits in July" → $19,775.35) rather than read off the prose. Accuracy touches include schema sample values, normalized ISO date columns, per-page period labels, and a guard that routes a suspicious empty result to RAG instead of reporting a confident zero.

Deliberately reduced from full CASSIA — no charts, no auth, no durable multi-session memory, no persistent "core." A **single sticky session** (survives refresh, dies on tab close) with a **New chat** reset. Bilingual; saves the whole thread to Work History.

#### 9. 🔍 GL Audit Review Packet — *LUCENT add-on*
Upload a company-level GL export (CSV/Excel) and get back a compact audit-review packet: a prioritized review queue, data-quality checks, the top flagged rows, and an evidence-request memo for each. Built on LUCENT's thesis — **ML finds, audit logic adjusts, GPT explains**:

- **ML finds** — an **IsolationForest** (scikit-learn, 200 trees) over six audit signals produces a raw anomaly tier. The reviewer's Detection Sensitivity setting drives contamination, and tiers are cut by quantile so the dial visibly changes the queue size.
- **Audit logic adjusts** — two moves, in fixed order. The **materiality cascade** (benchmark → FS 4-5% → performance 50% → transaction 80%) is the only step that can *lower* a tier. The **qualitative override** fires when two or more indicators co-occur on one row, escalating it one tier *above the raw ML tier* — so a small-dollar row that materiality buried can be restored. Labels stay PCAOB-aligned and deliberately non-conclusive (*Potential Material Weakness Indicator*, *Monitor — Below Escalation Threshold*).
- **GPT explains** — a three-block evidence memo per flagged row: **Why this row matters** / **Evidence to request** / **Not a conclusion**, with the relevant audit standard woven in as *design rationale* (AU-C 315, PCAOB AS 2401, COSO components, IT/limit controls). A banned-phrase scan runs on every memo.

The six signals — account-level amount z-score, round number, weekend posting, missing description, new vendor, near approval threshold — each map to a recognized red flag. Data-quality checks (hash total, cross-footing, date-in-period, account mapping) run before scoring and skip gracefully when optional columns are absent.

Deliberately reduced from standalone LUCENT: no charts, no full data dictionary, no seven-field memo, no Top 10/20 narrative, and the weak-label RandomForest similarity layer is dropped (it is inert without labels). Required columns are relaxed to `date, amount, account_name, vendor, description, journal_ref`. Bilingual — in Bilingual mode each language is generated as its own primary memo and interleaved, so neither half is a summary of the other. Exports a flagged CSV and a Markdown review packet, and saves to Work History.

> LUCENT indicates review priority only. It does not conclude fraud or issue audit opinions.

Each add-on is renamed by function and built on the same shared spine.

---

## 🏗️ Architecture

```
┌─────────────────────────┐      HTTP / JSON      ┌─────────────────────────────────┐
│  Next.js frontend       │  ◀──────────────────▶ │  FastAPI backend                │
│  (localhost:3000)       │                        │  (localhost:8000)               │
│                         │                        │                                 │
│  • Sidebar + tools/*    │                        │  routers/                       │
│  • Work History page    │                        │   • core         /api/journal   │
│  • Bilingual selector   │                        │                  /api/term      │
│  • Save-to-History      │                        │   • files        /api/analyze-  │
│    on every tool        │                        │                  file           │
│                         │                        │   • history      /api/history/* │
│                         │                        │   • reconcile    /api/reconcile │
│                         │                        │   • pdf          /api/pdf/ingest│
│                         │                        │   • consolidated /api/          │
│                         │                        │                  consolidated/* │
│                         │                        │   • chat         /api/chat/*    │
│                         │                        │   • gl_review    /api/gl-review/*│
└─────────────────────────┘                        └───────────┬─────────────────────┘
                                                                │
        ┌───────────────────────────────┬───────────────────────┼───────────────────────┐
        ▼                               ▼                        ▼                       ▼
┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
│ OpenAI GPT-4o-mini │   │ Claude Agent SDK   │   │ Claude PDF Skill   │   │ SQLite             │
│ journal · term ·   │   │ 1099 reconcile     │   │ statement ingest   │   │ Work History       │
│ file analyzer      │   │ orchestration      │   │ (+ rule fallback)  │   │ archive            │
└────────────────────┘   └────────────────────┘   └────────────────────┘   └────────────────────┘
```

The backend is organized into routers, with a shared `app/services/pdf/` package (ingestion + Source A + Source B) that both statement tools consume. The **Consolidated Workbook** add-on adds an `app/services/consolidated/` package that calls the shared PDF service per statement, then does the cross-statement aggregation, validation, and master-workbook generation on top. The **Data & Document Chat** add-on adds a self-contained `app/services/chat/` package — a schema-aware router, in-memory text-to-SQL, and in-memory RAG — with ChromaDB replaced by a NumPy cosine search, so it runs entirely on TAU's existing dependencies. The **GL Audit Review Packet** add-on adds `app/services/gl_review/`, which layers scikit-learn anomaly detection, a materiality/override scoring engine ported from LUCENT, and a standards-anchored memo generator; row memos are generated concurrently via a thread pool.

---

## 📂 Project structure

```
transaction-agent-ultimate/
├── .gitignore
├── README.md
├── .claude/skills/pdf/                 # Claude PDF Skill (copied in; not committed)
├── backend/                            # FastAPI (Python)
│   ├── .env                            # API keys — never committed
│   ├── requirements.txt
│   ├── tau_history.db                  # Work History (SQLite; not committed)
│   └── app/
│       ├── main.py                     # app factory, mounts routers (v0.10.0)
│       ├── config.py                   # typed settings
│       ├── db.py                        # SQLite init (history table)
│       ├── routers/
│       │   ├── core.py                 # /api/journal, /api/term
│       │   ├── files.py                # /api/analyze-file
│       │   ├── reconcile.py            # /api/reconcile/*
│       │   ├── history.py              # /api/history/*  (unified archive)
│       │   ├── pdf.py                  # /api/pdf/ingest (shared PDF service)
│       │   ├── consolidated.py         # /api/consolidated/* (Consolidated Workbook)
│       │   ├── chat.py                 # /api/chat/* (Data & Document Chat)
│       │   └── gl_review.py            # /api/gl-review/* (GL Audit Review Packet)
│       ├── services/
│       │   ├── openai_service.py
│       │   ├── prompts.py              # + bilingual (KO / EN / Bilingual)
│       │   ├── file_service.py
│       │   ├── reconciliation_service.py
│       │   ├── history_service.py      # save / list / get / delete / reset
│       │   ├── pdf/                     # shared PDF ingestion package
│       │   │   ├── transaction.py       # shared row contract
│       │   │   ├── classifier.py        # deterministic row classifier
│       │   │   ├── rule_extractor.py    # pdfplumber + regex engine
│       │   │   ├── skill_adapter.py     # Claude PDF Skill engine
│       │   │   ├── reconciliation.py    # Source A — reconciliation
│       │   │   ├── source_b.py          # Source B — extraction completeness
│       │   │   ├── service.py           # ingest_statement() facade
│       │   │   └── pdf_skill_prompt.md  # classification policy
│       │   └── consolidated/            # ⭐ Consolidated Workbook package
│       │       ├── vendor_normalizer.py       # canonical vendor names
│       │       ├── transaction_aggregator.py  # aggregate by vendor
│       │       ├── vendor_classifier_1099.py  # 1099-NEC / REVIEW / EXEMPT
│       │       ├── review_flag_engine.py       # per-statement review flags
│       │       ├── validation_engine.py        # cross-statement validation
│       │       ├── master_excel_generator.py   # 5-sheet master workbook
│       │       └── service.py                  # consolidate() facade
│       │   └── chat/                    # ⭐ Data & Document Chat package (in-memory)
│       │       ├── text_splitter.py            # recursive chunker (no LangChain)
│       │       ├── router.py                    # schema-aware sql / rag / general routing
│       │       ├── sql_engine.py                # CSV/Excel + PDF tables → in-memory SQLite
│       │       ├── rag_engine.py                # context-preserving chunks → cosine top-k
│       │       └── service.py                   # facade + session store
│       │   └── gl_review/                # ⭐ GL Audit Review Packet package
│       │       ├── features.py                  # the six audit signals
│       │       ├── anomaly.py                   # IsolationForest + quantile raw tier
│       │       ├── scoring.py                   # materiality cascade + qualitative override
│       │       ├── integrity.py                 # 4 data-quality checks
│       │       ├── anchors.py                   # audit-standard anchor map
│       │       ├── memo.py                      # 3-block evidence memo + guardrail
│       │       └── service.py                   # pipeline facade
│       └── models/
│           ├── schemas.py
│           ├── file_schemas.py
│           ├── reconciliation_schemas.py
│           └── history_schemas.py
│
└── frontend/                           # Next.js (React)
    ├── pages/
    │   ├── _app.js
    │   └── index.js                    # shell + routing
    ├── components/
    │   ├── Sidebar.js
    │   ├── WorkHistory.js
    │   ├── SaveToHistory.js
    │   ├── LangOverride.js
    │   ├── i18n.js
    │   ├── api.js
    │   └── tools/
    │       ├── JournalEntry.js
    │       ├── TermExplainer.js
    │       ├── FileAnalyzer.js
    │       ├── Reconcile.js
    │       ├── StatementReview.js       # Source A + Source B
    │       ├── ConsolidatedWorkbook.js
    │       ├── DataDocumentChat.js
    │       └── GLAuditReviewPacket.js    # ⭐ new
    └── styles/globals.css
```

---

## 📡 API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check (returns version) |
| POST | `/api/journal` | Generate a journal entry |
| POST | `/api/term` | Explain an accounting term |
| GET / POST / DELETE | `/api/history` | List / save / clear the Work History archive |
| GET / DELETE | `/api/history/{id}` | Get / delete one saved result |
| GET | `/api/history/{id}/download` | Re-download a saved result |
| POST | `/api/analyze-file` | Analyze an uploaded CSV / Excel / PDF |
| POST | `/api/reconcile/rule-based` | Rule-based 1099 reconciliation |
| POST | `/api/reconcile/agent` | Claude-Agent 1099 reconciliation |
| GET | `/api/reconcile/download/{id}` | Download the generated Excel |
| POST | `/api/pdf/ingest` | Shared statement ingestion → classified rows + Source A + Source B |
| POST | `/api/consolidated/analyze` | Multi-statement consolidation → master workbook |
| GET | `/api/consolidated/download/{req_id}/{file}` | Download the master workbook |
| POST | `/api/chat/upload` | ⭐ Load a CSV/Excel/PDF into a chat session (side action) |
| POST | `/api/chat/ask` | ⭐ Ask a question → routed to SQL / RAG / general |
| POST | `/api/chat/reset` | ⭐ Clear the chat session (new blank chat) |
| GET | `/api/chat/state` | What's currently loaded in the session |
| POST | `/api/gl-review/analyze` | ⭐ GL export + settings → review packet |
| GET | `/api/gl-review/download/{req_id}/{kind}` | ⭐ Flagged CSV or Markdown review memo |

`/api/pdf/ingest` accepts `pdf_file`, `engine` (`skill` \| `rule`), `model`, and `source`, and returns classified transactions, an activity breakdown, a `reconciliation` block (Source A), and an `extraction_check` block (Source B).

`/api/consolidated/analyze` accepts multiple `pdf_files[]`, an optional `vendor_csv`, plus `engine` and `model`, and returns a per-statement summary, cross-statement validation, and a downloadable 5-sheet master workbook.

`/api/gl-review/analyze` accepts a GL `file` plus entity type, benchmark, sensitivity, review period, top-N and language, and returns materiality thresholds, summary cards, integrity findings, the top flagged rows, the AI Review Packet, and per-row evidence memos.

`/api/chat/upload` accepts a `session_id` and a `file` (CSV/Excel → SQL table; PDF → RAG chunks, plus any ruled tables into SQLite). `/api/chat/ask` takes a `session_id`, `question`, and `language`, and returns the answer plus the route taken (`sql` / `rag` / `general`).

---

## 🚀 Quick start

### Prerequisites
- Python 3.10+ (tested on 3.13), Node.js 18+ with npm
- An **OpenAI API key** (journal, term, file analyzer)
- An **Anthropic API key** (1099 agent mode, Statement Review + Consolidated skill engine)

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env`:
```env
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Start it:
```bash
uvicorn app.main:app --reload --port 8000
```
Verify at **http://localhost:8000/docs**.

### Statement tools — one-time skill setup
The skill engine (used by both Statement Review and Consolidated Workbook) needs the Claude PDF Skill reachable from the project root:
```bash
mkdir -p .claude/skills
cp -R /path/to/PREPARE/.claude/skills/pdf .claude/skills/pdf
```
(Or install it user-level at `~/.claude/skills/pdf` to share across projects.) Without it, the skill engine returns a clean failure and the rule engine still works.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:3000**.

---

## 🌐 Bilingual support
A global language selector (Korean / English / Bilingual) applies to every tool, with a per-tool override where it matters. Korean output follows K-IFRS phrasing; English follows IFRS. In bilingual mode, Korean is shown first, then English.

---

## 🗺️ Roadmap

- **v0.5.0** — journal, term, history, file analyzer, 1099 reconciliation (rule-based + Claude Agent).
- **v0.7.0** — unified Work History archive, shared PDF ingestion service, bilingual system, and the **Statement Review** add-on (first PREPARE tool).
- **v0.8.0** — the **Consolidated Workbook** add-on (second PREPARE tool: cross-statement vendor aggregation + 5-sheet master workbook), and **Source B** extraction-completeness, now shared by both statement tools.
- **v0.9.0** — the **Data & Document Chat** add-on (first CASSIA tool: general Q&A + text-to-SQL + RAG, fully in-memory), with schema-aware routing and PDF-table querying. Reduced hard from full CASSIA — no charts, auth, or persistent core.
- **v0.10.0** ⭐ *(current)* — the **GL Audit Review Packet** add-on (LUCENT: IsolationForest anomaly tiering + materiality cascade + qualitative override + standards-anchored evidence memos). **The convergence roadmap is complete** — all four planned add-ons are in the hub.
- **Next** — polish rather than new tools. GL Audit Review: pivot the flagged table into a collapsible full view, optional Excel workbook export, and a period-over-period comparison. Data & Document Chat: pivot key/value summary blocks into named columns, and broaden ingestion (non-ruled/scanned PDFs, non-US number and non-UTF-8 encodings).
- **Before any outside-user deployment** — server-issued session IDs and session-store eviction for the chat add-on, and per-request size limits on GL uploads (the current client-generated session ID, module-level store, and in-memory export cache are intended for local single-user use).

The architecture is deliberately additive: each add-on plugs into the shared spine without changing the tools already in place.

---

## 🛠️ Tech stack

**Backend:** FastAPI, pydantic-settings, OpenAI Python SDK, Claude Agent SDK, Claude PDF Skill (Sonnet), pdfplumber, pandas, openpyxl, SQLite (stdlib), NumPy (in-memory vector search for the chat add-on — no ChromaDB/LangChain), scikit-learn (IsolationForest for the GL review add-on).
**Frontend:** Next.js, React, react-markdown + remark-gfm, CSS (navy professional theme).
**AI models:** OpenAI GPT-4o-mini (journal / term / file analyzer / Data & Document Chat / GL Audit Review Packet) and text-embedding-3-small (chat RAG retrieval); Claude Sonnet via the PDF Skill (statement ingestion + consolidation); Claude Haiku / Opus (1099 agent orchestration).

---

## ⚠️ Disclaimer

Built for educational and portfolio purposes. It is not a substitute for professional accounting advice — always have AI-generated output reviewed by a qualified accountant or CPA before use in real bookkeeping, tax filings, or financial reporting.

---

## 🙏 Acknowledgments

Built as part of an accounting-to-AI-engineering portfolio, converging a family of real-workflow prototypes into one cohesive hub — turning manual, repetitive accounting chores into an AI-assisted workflow that saves time per client.

Frontend: Next.js · Backend: FastAPI · AI: OpenAI GPT-4o-mini + Claude Agent SDK + Claude PDF Skill
