# 📊 Transaction Agent Ultimate (TAU)

**An AI-powered accounting utility hub** — a **FastAPI backend** and **Next.js frontend** that brings journal-entry generation, terminology help, file analysis, statement review, and an end-to-end 1099 workflow together in one bilingual (Korean / English) interface.

TAU is designed to **converge a family of accounting tools into a single hub.** Rather than shipping separate apps, each capability is folded in as a compact, function-named **add-on** that sits on a shared spine — one unified work archive, one PDF ingestion engine, one language setting. Standalone prototypes (PREPARE, CASSIA, LUCENT) are being reduced to add-ons and brought in one at a time.

> **Version 0.7.0** — adds the unified Work History archive, the shared PDF ingestion service (Claude PDF Skill + rule engine), and the first PREPARE add-on: **Statement Review**.

---

## 🧱 The shared spine

Every tool reads from and writes to three shared services. This is what keeps the hub cohesive as add-ons are added:

- **Work History** — a single SQLite-backed archive (`backend/tau_history.db`). Any tool can save a result; the Work History page lists everything across all tools, filters by tool, reopens a saved result, re-downloads it, or clears the archive.
- **PDF ingestion service** — one engine that turns a statement PDF into classified transactions plus a reconciliation snapshot. Two backends: the **Claude PDF Skill** (accurate, column-aware) and a **rule engine** (instant, free). Consumed by every statement-oriented tool.
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

#### 6. 📄 Statement Review ⭐ *new — first PREPARE add-on*
Upload one statement and get a per-statement bookkeeping review:
- **Row-level classification** — every transaction labeled (vendor payment, check, deposit, payroll, transfer, fee, interest), each marked included / excluded for 1099 aggregation with an exclusion reason.
- **Statement reconciliation** — the statement's own stated figures laid out deterministically: `beginning + deposits − withdrawals − checks − transfers − fees = calculated ending`, compared against the reported ending, with a **Balanced / Off** verdict. Built on the "transcribe, don't compute" principle: the model transcribes the stated balances, and the arithmetic runs in one place on the backend.
- **Two modes** — *Quick preview* (rule engine, instant, free) and *Full analysis* (Claude PDF Skill, column-aware, ~1–4 min).
- Saves a clean markdown artifact to Work History.

### Planned add-ons (the convergence roadmap)

| Add-on | Source app | Function |
|--------|-----------|----------|
| **Consolidated Workbook** | PREPARE | Cross-statement vendor aggregation and $600/entity 1099 eligibility rollup (the vendor-level workbook). |
| **Data & Document Chat** | CASSIA | Conversational retrieval over your own records and documents. |
| **GL Audit Review Packet** | LUCENT | Pre-audit checks and a review packet over the general ledger. |

Each is a compact add-on renamed by function, built on the same shared spine.

---

## 🏗️ Architecture

```
┌─────────────────────────┐      HTTP / JSON      ┌─────────────────────────────┐
│  Next.js frontend       │  ◀──────────────────▶ │  FastAPI backend            │
│  (localhost:3000)       │                        │  (localhost:8000)           │
│                         │                        │                             │
│  • Sidebar + tools/*    │                        │  routers/                   │
│  • Work History page    │                        │   • core     /api/journal   │
│  • Bilingual selector   │                        │              /api/term      │
│  • Save-to-History      │                        │   • files    /api/analyze-  │
│    on every tool        │                        │              file           │
│                         │                        │   • history  /api/history/* │
│                         │                        │   • reconcile /api/reconcile│
│                         │                        │   • pdf      /api/pdf/ingest│
└─────────────────────────┘                        └───────────┬─────────────────┘
                                                                │
        ┌───────────────────────────────┬───────────────────────┼───────────────────────┐
        ▼                               ▼                        ▼                       ▼
┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
│ OpenAI GPT-4o-mini │   │ Claude Agent SDK   │   │ Claude PDF Skill   │   │ SQLite             │
│ journal · term ·   │   │ 1099 reconcile     │   │ statement ingest   │   │ Work History       │
│ file analyzer      │   │ orchestration      │   │ (+ rule fallback)  │   │ archive            │
└────────────────────┘   └────────────────────┘   └────────────────────┘   └────────────────────┘
```

The backend is organized into routers, with a shared `app/services/pdf/` package that both statement tools consume.

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
│       ├── main.py                     # app factory, mounts routers (v0.7.0)
│       ├── config.py                   # typed settings
│       ├── db.py                        # SQLite init (history table)
│       ├── routers/
│       │   ├── core.py                 # /api/journal, /api/term
│       │   ├── files.py                # /api/analyze-file
│       │   ├── reconcile.py            # /api/reconcile/*
│       │   ├── history.py              # /api/history/*  (unified archive)
│       │   └── pdf.py                  # /api/pdf/ingest (shared PDF service)
│       ├── services/
│       │   ├── openai_service.py
│       │   ├── prompts.py              # + bilingual (KO / EN / Bilingual)
│       │   ├── file_service.py
│       │   ├── reconciliation_service.py
│       │   ├── history_service.py      # save / list / get / delete / reset
│       │   └── pdf/                     # ⭐ shared PDF ingestion package
│       │       ├── transaction.py       # shared row contract
│       │       ├── classifier.py        # deterministic row classifier
│       │       ├── rule_extractor.py    # pdfplumber + regex engine
│       │       ├── skill_adapter.py     # Claude PDF Skill engine
│       │       ├── reconciliation.py    # Source-A reconciliation (deterministic)
│       │       ├── service.py           # ingest_statement() facade
│       │       └── pdf_skill_prompt.md  # classification policy
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
    │       └── StatementReview.js      # ⭐ new
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
| POST | `/api/pdf/ingest` | ⭐ Shared statement ingestion → classified rows + reconciliation |

`/api/pdf/ingest` accepts `pdf_file`, `engine` (`skill` \| `rule`), `model`, and `source`, and returns classified transactions, an activity breakdown, and — on the skill engine — a reconciliation block.

---

## 🚀 Quick start

### Prerequisites
- Python 3.10+ (tested on 3.13), Node.js 18+ with npm
- An **OpenAI API key** (journal, term, file analyzer)
- An **Anthropic API key** (1099 agent mode, Statement Review skill engine)

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

### Statement Review — one-time skill setup
The skill engine needs the Claude PDF Skill reachable from the project root:
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
- **v0.7.0** ⭐ *(current)* — unified Work History archive, shared PDF ingestion service, bilingual system, and the **Statement Review** add-on (first PREPARE tool).
- **Next** — bring in PREPARE's `validation_engine` to add the extraction-completeness half of the Statement Review diagnostic.
- **Then** — **Consolidated Workbook** (PREPARE Tool 2): cross-statement vendor aggregation and $600/entity 1099 eligibility.
- **Later** — **Data & Document Chat** (CASSIA) and **GL Audit Review Packet** (LUCENT) add-ons.
- **Housekeeping** — move to a venv-per-app layout to resolve the numpy/langchain vs. numpy 2.x conflict before CASSIA lands, then lock reproducible dependencies.

The architecture is deliberately additive: each add-on plugs into the shared spine without changing the tools already in place.

---

## 🛠️ Tech stack

**Backend:** FastAPI, pydantic-settings, OpenAI Python SDK, Claude Agent SDK, Claude PDF Skill (Sonnet), pdfplumber, pandas, openpyxl, SQLite (stdlib).
**Frontend:** Next.js, React, react-markdown + remark-gfm, CSS (navy professional theme).
**AI models:** OpenAI GPT-4o-mini (journal / term / file analyzer); Claude Sonnet via the PDF Skill (statement ingestion); Claude Haiku / Opus (1099 agent orchestration).

---

## ⚠️ Disclaimer

Built for educational and portfolio purposes. It is not a substitute for professional accounting advice — always have AI-generated output reviewed by a qualified accountant or CPA before use in real bookkeeping, tax filings, or financial reporting.

---

## 🙏 Acknowledgments

Built as part of an accounting-to-AI-engineering portfolio, converging a family of real-workflow prototypes into one cohesive hub — turning manual, repetitive accounting chores into an AI-assisted workflow that saves time per client.

Frontend: Next.js · Backend: FastAPI · AI: OpenAI GPT-4o-mini + Claude Agent SDK + Claude PDF Skill
