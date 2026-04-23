# 📊 Transaction Agent Ultimate (TAU)

AI-powered accounting assistant with a **FastAPI backend** and **Next.js frontend**, integrating **OpenAI GPT-4o-mini** for accounting assistance and the **Claude Agent SDK** for autonomous 1099 reconciliation.

TAU is a comprehensive AI suite for accountants and finance professionals — combining journal entry generation, terminology explanations, session history, file analysis, and an end-to-end 1099 pre-reconciliation workflow in a single bilingual interface (Korean / English).

---

## 🎯 Features

### 1. 📊 Journal Entry Generator (분개 도우미)
- Input any transaction description in Korean or English (e.g., `"사무용품 100,000원을 현금으로 구매"`)
- Get a complete debit/credit journal entry in a formatted table
- Recommended account titles with plain-language explanations
- Step-by-step accounting principle breakdown
- Supports K-IFRS (Korean) and IFRS (English) standards

### 2. 📖 Term Explainer (용어 설명)
- Enter any accounting term (e.g., `"감가상각"`, `"accrual basis"`)
- Bilingual explanation (Korean + English) side-by-side
- Journal entry example in a formatted table
- Practical tips for real-world usage

### 3. 📋 Session History (분개 히스토리)
- Automatically saves every journal entry generated during the session
- Expandable cards to review past entries
- One-click history reset
- Persists across page navigation within the session

### 4. 📁 File Analyzer (파일 분석기)
- Upload CSV, Excel (.xlsx), or PDF files
- Pandas pipeline: cleans QuickBooks-style GL exports (strips headers, totals, spacer columns)
- Anomaly detection: Z-score based outlier flagging (2.5 std deviations)
- Duplicate vendor detection: catches formatting inconsistencies
- PDF table extraction: uses pdfplumber to extract tables from any PDF
- GPT analysis: AI-generated financial summary with recommended actions
- Data preview table with currency formatting

### 5. 📑 1099 Pre-Reconciliation Worksheet (1099 정산 워크시트) ⭐ *New*
- Upload a bank or credit card statement (PDF) + optional vendor master list (CSV)
- Extracts all transactions, normalizes vendor names (handles "AMZN Mktp" → "Amazon"), aggregates by canonical vendor
- Identifies vendors crossing the $600 1099 threshold
- Flags vendors that need human review (low-confidence matches, multiple name variants)
- Generates a three-sheet accountant-grade Excel workbook (Vendor Summary / Transactions / Summary Stats)
- **Two processing modes:**
  - **Rule-Based mode** — fast, deterministic, no API cost. Pure Python pipeline.
  - **Claude Agent mode** — the Claude Agent SDK autonomously orchestrates the extraction, normalization, aggregation, and Excel generation tools. Produces a plain-English analysis of the results. Uses Anthropic API credits.
- Model selection for agent mode: Haiku 4.5 (cost-efficient) or Opus 4.7 (highest quality)
- Download-ready Excel output with review-flagged rows highlighted

> **Runs as an add-on to TAU AND as a standalone server.** The 1099 reconciliation module can also be run independently at `http://localhost:8000` via its own FastAPI entry point — see the *Standalone Mode* section below.

### 🛡️ Error Resilience
- 429 (Quota exceeded) → friendly message with billing link
- 401 (Invalid API key) → instructions to fix `.env`
- 500 (Server error) → retry suggestion
- Network issues → backend connection check reminder

### 🌐 Bilingual Support
- Full Korean (K-IFRS) and English (IFRS) support
- Language toggle in the sidebar applies to all pages
- API responses are localized based on user selection

---

## 🏗️ Architecture

```
┌─────────────────────────┐       HTTP        ┌────────────────────────────┐
│  Next.js Frontend       │  ──── JSON ────▶  │  FastAPI Backend           │
│  (localhost:3000)       │  ◀──── JSON ────  │  (localhost:8000)          │
│                         │                    │                            │
│  • React UI + Sidebar   │                    │  • POST /api/journal       │
│  • 5-page navigation    │                    │  • POST /api/term          │
│  • Markdown rendering   │                    │  • GET/DELETE /api/history │
│  • File upload          │                    │  • POST /api/analyze-file  │
│  • Error display        │                    │  • POST /api/reconcile/*   │
└─────────────────────────┘                    │  • GET  /api/reconcile/    │
                                               │         download/{id}      │
                                               └─────────────┬──────────────┘
                                                             │
                                    ┌────────────────────────┼────────────────────────┐
                                    ▼                                                 ▼
                        ┌───────────────────────┐                         ┌────────────────────────┐
                        │  OpenAI GPT-4o-mini   │                         │  Claude Agent SDK      │
                        │  (journal, term,      │                         │  (1099 reconciliation) │
                        │   file analyzer)      │                         │                        │
                        └───────────────────────┘                         └────────────────────────┘
```

Two AI providers coexist — each feature uses the best tool for the job.

---

## 📂 Project Structure

```
transaction-agent-ultimate/
├── .gitignore
├── backend/                            # FastAPI (Python)
│   ├── .env                            # API keys (never committed)
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py                     # All FastAPI endpoints
│       ├── config.py                   # Typed settings (pydantic-settings)
│       ├── services/
│       │   ├── openai_service.py       # OpenAI API client + error handling
│       │   ├── prompts.py              # System prompts (few-shot + CoT)
│       │   ├── file_service.py         # Pandas cleaning + PDF parsing
│       │   ├── file_prompts.py         # GPT prompts for file analysis
│       │   └── reconciliation_service.py  # ⭐ 1099 pipeline (rule-based + agent)
│       └── models/
│           ├── schemas.py              # Journal / term / history schemas
│           ├── file_schemas.py         # File analyzer schemas
│           └── reconciliation_schemas.py  # ⭐ Reconciliation response schema
│
├── frontend/                           # Next.js (React)
│   ├── package.json
│   ├── next.config.js
│   ├── pages/
│   │   ├── _app.js                     # Global CSS loader
│   │   └── index.js                    # All 5 pages + sidebar (single-page app)
│   └── styles/
│       └── globals.css                 # Navy professional theme
│
└── README.md                           # This file
```

---

## 📡 API Endpoints

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|--------------|
| GET | `/` | Health check | — |
| POST | `/api/journal` | Generate journal entry | `{"transaction": "...", "language": "한국어"}` |
| POST | `/api/term` | Explain accounting term | `{"term": "...", "language": "한국어"}` |
| GET | `/api/history` | Get all saved entries | — |
| DELETE | `/api/history` | Clear history | — |
| POST | `/api/analyze-file` | Analyze uploaded file | `multipart/form-data` (CSV, Excel, PDF) |
| POST | `/api/reconcile/rule-based` | ⭐ Rule-based 1099 reconciliation | `multipart/form-data` (PDF + optional CSV) |
| POST | `/api/reconcile/agent` | ⭐ Claude-Agent-powered reconciliation | `multipart/form-data` + `model` form field |
| GET | `/api/reconcile/download/{file_id}` | ⭐ Download generated Excel | — |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (tested on 3.13)
- **Node.js 18+** (tested on 24) with **npm**
- An **OpenAI API key** (for journal, term, file analyzer features)
- An **Anthropic API key** (for 1099 reconciliation agent mode)

### 1. Clone and configure

```bash
git clone <repository-url>
cd transaction-agent-ultimate
```

### 2. Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create `backend/.env`:

```env
OPENAI_API_KEY=sk-proj-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-api03-your-anthropic-key-here
```

> ⚠️ Never commit `.env`. It's in `.gitignore` by default.

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Verify at **http://localhost:8000/docs** — you should see all 9 endpoints.

### 3. Frontend setup

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## 🧪 Standalone Mode (1099 Reconciliation only)

The 1099 reconciliation module is **also available as a standalone server** that runs independently from the full TAU suite. Use this when you want to ship or demo only the reconciliation feature without the journal/term/history/file-analyzer pages.

### Standalone repository structure

```
pdf_to_excel_app/
├── backend/
│   ├── vendor_normalizer.py
│   ├── transaction_aggregator.py
│   ├── pdf_extractor.py
│   ├── excel_generator.py
│   └── pipeline.py
├── frontend/
│   └── index.html               # Self-contained single-page app
├── samples/
│   ├── sample_bank_statement_2024.pdf
│   └── known_vendors.csv
├── server.py                    # FastAPI entry point
├── agent_app.py                 # Claude Agent SDK orchestrator
├── agent_tools.py               # Tool definitions (MCP server)
├── run_agent.py                 # CLI entry point
└── .env
```

### How to run the standalone server

```bash
cd pdf_to_excel_app
source venv/bin/activate   # or create one: python3 -m venv venv
pip install fastapi uvicorn python-multipart pdfplumber openpyxl reportlab claude-agent-sdk python-dotenv

# Create .env with ANTHROPIC_API_KEY
echo 'ANTHROPIC_API_KEY=sk-ant-api03-your-key' > .env

uvicorn server:app --reload --port 8000
```

Open **http://localhost:8000** — the standalone frontend is served at the root, no separate frontend server needed.

### Choosing between modes

| Mode | Use when |
|------|----------|
| **TAU integrated** (`/api/reconcile/*`) | You want reconciliation alongside journal, term, history, and file analyzer in one cohesive suite |
| **Standalone** (`pdf_to_excel_app/server.py`) | You want only the reconciliation feature — fewer dependencies, simpler deployment, quicker demo |

Both modes share the same underlying logic and produce identical Excel output. The TAU version adds integration with the bilingual UI and navy theme; the standalone version ships its own single-file HTML frontend.

---

## 🎨 Processing Mode Comparison

The 1099 reconciliation feature offers two processing modes side-by-side:

| Aspect | Rule-Based | Claude Agent SDK |
|--------|-----------|------------------|
| **Speed** | Instant (< 2 sec) | 10–30 seconds |
| **Cost** | Free | ~$0.01 (Haiku) / ~$0.09 (Opus) per run |
| **Determinism** | Fully deterministic | Agent decides tool order |
| **Output** | Excel + stats | Excel + stats + plain-English Claude analysis |
| **Best for** | Development, repeated processing, batch jobs | Demonstrating AI orchestration, handling ambiguous cases, explanatory output |

Toggle between modes via the UI. Results are identical in structure — the agent mode adds a natural-language summary explaining what it did.

---

## 🧠 How the Claude Agent Mode Works

When the user selects Claude Agent mode, the backend spawns a `ClaudeSDKClient` session. The agent is given access to five custom tools that wrap the Python reconciliation modules:

1. `extract_pdf_transactions(pdf_path)` — pulls transactions via pdfplumber
2. `load_vendor_list(csv_path)` — loads the canonical vendor master
3. `normalize_vendors()` — runs fuzzy matching and entity-type extraction
4. `aggregate_by_vendor()` — groups transactions, computes totals
5. `generate_excel_report(output_path)` — produces the final workbook

The agent autonomously decides the order of tool calls, handles any errors, and produces a natural-language summary describing the results. All tool execution is auditable — the backend logs every tool call with parameters.

---

## 🧪 Testing

Test fixtures are included in the standalone app's `samples/` folder:

- **`sample_bank_statement_2024.pdf`** — 48-transaction year-long test statement with intentional edge cases (vendor name variants, check payments, multiple payments to same vendor, entity type variety)
- **`known_vendors.csv`** — optional vendor master file with 11 canonical names

Expected output when processed:
- 48 transactions extracted
- 16 unique canonical vendors
- $19,474.87 total reconciled
- 9 vendors crossing the $600 threshold
- 8 vendors flagged for human review

---

## ⚠️ Known Limitations

This is an MVP intended for portfolio demonstration. Real-world deployment would require:

- **Bank statement variation** — the regex patterns are tuned for the sample PDF format. Real statements from different banks (Chase, BofA, Wells Fargo, Amex, etc.) use different layouts and may produce fewer extractions or require layout-specific parsing logic.
- **Scanned PDFs** — image-based (scanned) PDFs produce zero transactions. Session 4 adds OCR support via Tesseract.
- **Full 1099 rule logic** — the current `1099 Eligible` column in Excel is marked "TBD". Session 4 implements full IRS logic (attorney exception, merchandise exclusion, medical payments, etc.).
- **W-9 tracking** — no persistent vendor master across sessions. Session 4 adds SQLite persistence.
- **Cross-validation** — no comparison against client-reported amounts. Session 4 adds this.
- **LLM-based fallback extraction** — when regex fails, the agent should be able to extract transactions directly from raw PDF text. Session 4 adds this tool.

The architecture is designed so all of these are additive improvements — none require changes to the existing code.

---

## 🛠️ Tech Stack

**Backend:**
- FastAPI 0.x
- pydantic-settings (typed settings)
- OpenAI Python SDK (journal / term / file analyzer)
- Claude Agent SDK 0.1.65 (reconciliation orchestration)
- pdfplumber (PDF table extraction)
- pandas (data cleaning)
- openpyxl (Excel generation)

**Frontend:**
- Next.js 14
- React 18
- react-markdown + remark-gfm (Markdown rendering)
- CSS modules (navy professional theme)

**AI Models:**
- OpenAI GPT-4o-mini (journal, term, file analyzer)
- Claude Haiku 4.5 (default agent model)
- Claude Opus 4.7 (high-quality agent mode)

---

## 📝 License & Disclaimer

⚠️ **This application is built for educational and portfolio demonstration purposes.** It is not a substitute for professional accounting advice. Always consult a licensed accountant or CPA for real accounting and tax work.

AI-generated output should be reviewed by a qualified professional before being used in production bookkeeping, tax filings, or financial reporting.

---

## 🗺️ Roadmap

- **v0.4.0** — Journal, term, history, file analyzer (OpenAI GPT-4o-mini)
- **v0.5.0** ⭐ *(current)* — 1099 pre-reconciliation with rule-based and Claude Agent SDK modes
- **v0.6.0** *(planned)* — Full 1099 eligibility logic, W-9 tracking, cross-validation, LLM fallback extraction
- **v0.7.0** *(planned)* — Frontend redesign for professional polish, expanded bilingual coverage
- **v1.0.0** *(planned)* — Production-ready release with persistent storage, authentication, and multi-client support

---

## 🙏 Acknowledgments

Built as part of an accounting-to-AI-engineering career transition portfolio. Special thanks to the mentor who framed the project around real-world Rowshan & Co. workflow pain points — turning manual 1099 reconciliation chaos into an AI-assisted workflow that could actually save accountants hours per client.

Frontend: Next.js | Backend: FastAPI | AI: OpenAI GPT-4o-mini + Claude Agent SDK
