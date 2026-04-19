# 📊 Transaction Agent Ultimate

AI-powered accounting assistant with separated **FastAPI backend** and **Next.js frontend**, following SOTA architecture patterns. Features journal entry generation, term explanation, session history, and **file analysis with PDF parsing**.

Enter a transaction description in Korean or English, and the AI generates proper **debit/credit journal entries** with account recommendations and explanations. Upload CSV, Excel, or PDF files for **automated data cleaning and AI-powered financial analysis**.

## Architecture

```
┌─────────────────────────┐         ┌──────────────────────────────┐
│   Next.js Frontend      │  HTTP   │    FastAPI Backend            │
│   (localhost:3000)       │ ──JSON──│    (localhost:8000)           │
│                         │ ──JSON──│                              │
│ • React UI + Sidebar    │         │ • POST /api/journal          │
│ • 4-page navigation     │         │ • POST /api/term             │
│ • Markdown rendering    │         │ • GET  /api/history          │
│ • File upload           │         │ • DELETE /api/history        │
│ • Error display         │         │ • POST /api/analyze-file     │
└─────────────────────────┘         └──────────────┬───────────────┘
                                                   │
                                            ┌──────▼──────┐
                                            │ OpenAI GPT  │
                                            │  4o-mini    │
                                            └─────────────┘
```

## Features

### 📊 Journal Entry Generator (분개 도우미)
- Input any transaction description (e.g., "사무용품 100,000원을 현금으로 구매")
- Receive complete debit/credit journal entry in formatted table
- Recommended account titles with explanations
- Step-by-step accounting principle breakdown
- Supports K-IFRS (Korean) and IFRS (English) standards

### 📖 Accounting Term Explainer (용어 설명)
- Enter any accounting term (e.g., "감가상각")
- Bilingual explanation (Korean + English)
- Journal entry example with formatted table
- Practical tips for real-world usage

### 📋 Session History (분개 히스토리)
- Automatically saves every journal entry generated
- Expandable cards to review past entries
- One-click history reset
- Persists across page navigation within the session

### 📁 File Analyzer (파일 분석기)
- Upload CSV, Excel (.xlsx), or PDF files
- **Pandas pipeline**: Cleans QuickBooks GL exports (strips headers, totals, spacer columns)
- **Anomaly detection**: Z-score based outlier flagging (2.5 std deviations)
- **Duplicate vendor detection**: Catches formatting inconsistencies
- **PDF table extraction**: Uses pdfplumber to extract tables from any PDF
- **GPT analysis**: AI-generated financial summary with recommended actions
- Data preview table with currency formatting

### 🛡️ Error Resilience
- 429 Quota exceeded → Friendly message with billing link
- 401 Invalid API key → Instructions to fix `.env`
- 500 Server error → Retry suggestion
- Network issues → Backend connection check reminder

### 🌐 Bilingual Support
- Full Korean (K-IFRS) and English (IFRS) support
- Language toggle in sidebar applies to all pages

## Project Structure

```
transaction-agent-ultimate/
├── .gitignore
├── backend/                          # FastAPI (Python)
│   ├── .env                          # API key (never committed)
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI endpoints + history
│   │   ├── config.py                 # Typed settings (pydantic-settings)
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── openai_service.py     # OpenAI API client + error handling
│   │   │   ├── prompts.py            # System prompts (few-shot + CoT)
│   │   │   ├── file_service.py       # Pandas cleaning + PDF parsing
│   │   │   └── file_prompts.py       # GPT prompts for file analysis
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── schemas.py            # Pydantic request/response models
│   │       └── file_schemas.py       # File analysis response models
│
├── frontend/                         # Next.js (React)
│   ├── package.json
│   ├── next.config.js
│   ├── pages/
│   │   ├── _app.js                   # Global CSS loader
│   │   └── index.js                  # All 4 pages + sidebar (single-page app)
│   └── styles/
│       └── globals.css               # Navy professional theme
```

## API Endpoints

| Method | Endpoint | Description | Request Body |
|--------|----------|-------------|-------------|
| GET | `/` | Health check | — |
| POST | `/api/journal` | Generate journal entry | `{"transaction": "...", "language": "한국어"}` |
| POST | `/api/term` | Explain accounting term | `{"term": "...", "language": "한국어"}` |
| GET | `/api/history` | Get all saved entries | — |
| DELETE | `/api/history` | Clear history | — |
| POST | `/api/analyze-file` | Analyze uploaded file | `multipart/form-data` (CSV, Excel, PDF) |

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+ (download from [nodejs.org](https://nodejs.org))
- OpenAI API key (get from [platform.openai.com/api-keys](https://platform.openai.com/api-keys))

### Terminal 1 — Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Mac/Linux
pip install -r requirements.txt
```

Create `backend/.env`:
```
OPENAI_API_KEY=sk-proj-your-key-here
```

Start the backend:
```bash
python3 -m uvicorn app.main:app --reload --port 8000
```

Verify: http://localhost:8000 → `{"status":"ok"}`

### Terminal 2 — Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open: http://localhost:3000

## SOTA Patterns Applied

| Pattern | Implementation |
|---------|---------------|
| Separated frontend/backend | Next.js (port 3000) + FastAPI (port 8000) |
| pydantic-settings | Typed config from `.env` — validated at startup |
| Pydantic models | `JournalEntryRequest`, `APIResponse` for all API contracts |
| Services layer | Business logic in `services/` — separated from API routes |
| Centralized error handling | Single `_call_openai()` catches all error types |
| Component-based UI | Sidebar, pages, result cards as React components |
| Multi-page navigation | 4 pages with sidebar — matches Streamlit MPA pattern |
| CORS middleware | Secure cross-origin requests between frontend and backend |

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js + React | User interface with sidebar navigation |
| Styling | CSS | Navy professional theme with centered layout |
| Markdown | react-markdown + remark-gfm | Renders tables and formatted content |
| Backend | FastAPI | REST API endpoints |
| AI | OpenAI GPT-4o-mini | Journal entry, term generation, file analysis |
| Data Processing | pandas + openpyxl | CSV/Excel cleaning and anomaly detection |
| PDF Parsing | pdfplumber | Table extraction from PDF documents |
| Validation | Pydantic | Request/response type safety |
| Config | pydantic-settings | Environment variable management |

## Evolution

| Version | Architecture | Features |
|---------|-------------|----------|
| Session 1 v1 | Single `app.py` (354 lines) | Basic journal entry, no error handling |
| Session 1 v2 | 3 Python files | Added error handling, file separation |
| Session 2 SOTA | `src/` layout (17 files) | Typed config, multi-page, pytest |
| Ultimate v0.2.0 | FastAPI + Next.js | Full stack, all 3 pages, formatted tables, history API |
| Ultimate v0.4.0 | FastAPI + Next.js | +File Analyzer, PDF parsing, navy theme, anomaly detection |

## Author

**Sang-Hyun Seong** — Baruch College. Built as part of the Gen AI × Accounting curriculum (Global AI Bootcamp).
