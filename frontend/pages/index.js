// pages/index.js
// ============================================================
// SOTA Next.js Frontend — All 4 pages with sidebar
// ============================================================
// - Page 1: Journal Entry (분개 도우미)
// - Page 2: Term Explainer (용어 설명)
// - Page 3: History (분개 히스토리)
// - Page 4: File Analyzer (파일 분석기) — CSV, Excel, PDF
// ============================================================

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_BASE = "http://localhost:8000";

export default function Home() {
  // ── State ──
  const [activePage, setActivePage] = useState("journal");
  const [language, setLanguage] = useState("한국어");
  const [transaction, setTransaction] = useState("");
  const [term, setTerm] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [expandedId, setExpandedId] = useState(null);

  // ── File Analyzer state ──
  const [fileResult, setFileResult] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState("");

  // ── Fetch history when switching to history page ──
  useEffect(() => {
    if (activePage === "history") {
      fetchHistory();
    }
  }, [activePage]);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/history`);
      const data = await res.json();
      setHistory(data.history || []);
    } catch {
      setHistory([]);
    }
  };

  // ── API call: Journal Entry ──
  const handleJournalSubmit = async () => {
    if (!transaction.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/journal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transaction, language }),
      });
      setResult(await res.json());
    } catch {
      setResult({ success: false, error: "백엔드 서버에 연결할 수 없습니다. FastAPI가 localhost:8000에서 실행 중인지 확인해주세요." });
    }
    setLoading(false);
  };

  // ── API call: Term Explanation ──
  const handleTermSubmit = async () => {
    if (!term.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/term`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ term, language }),
      });
      setResult(await res.json());
    } catch {
      setResult({ success: false, error: "백엔드 서버에 연결할 수 없습니다." });
    }
    setLoading(false);
  };

  // ── Clear history ──
  const handleClearHistory = async () => {
    try {
      await fetch(`${API_BASE}/api/history`, { method: "DELETE" });
      setHistory([]);
    } catch {}
  };

  // ── API call: File Upload & Analysis ──
  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setFileLoading(true);
    setFileError("");
    setFileResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_BASE}/api/analyze-file`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (data.success) {
        setFileResult(data);
      } else {
        setFileError(data.error || "File processing failed.");
      }
    } catch (err) {
      setFileError("Network error — is the backend running on port 8000?");
    } finally {
      setFileLoading(false);
    }
  };

  // ── Example transactions ──
  const examples = [
    "사무용품 100,000원을 현금으로 구매",
    "거래처에 상품 500,000원을 외상으로 판매",
    "은행에서 1,000,000원을 대출받음",
    "직원 급여 3,000,000원을 보통예금에서 이체",
    "건물 임대료 200,000원을 현금으로 지급",
  ];

  // ── Navigate and reset ──
  const navigateTo = (page) => {
    setActivePage(page);
    setResult(null);
  };

  return (
    <div className="app-layout">

      {/* ════════ SIDEBAR ════════ */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <span className="sidebar-logo">📊</span>
          Transaction Agent
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          <button className={`nav-item ${activePage === "journal" ? "active" : ""}`} onClick={() => navigateTo("journal")}>
            📊 분개 도우미
          </button>
          <button className={`nav-item ${activePage === "term" ? "active" : ""}`} onClick={() => navigateTo("term")}>
            📖 용어 설명
          </button>
          <button className={`nav-item ${activePage === "history" ? "active" : ""}`} onClick={() => navigateTo("history")}>
            📋 분개 히스토리
          </button>
          <button className={`nav-item ${activePage === "file" ? "active" : ""}`} onClick={() => navigateTo("file")}>
            📁 파일 분석기
          </button>
        </nav>

        <div className="sidebar-divider" />

        {/* Language selector */}
        <div className="sidebar-label">응답 언어 선택:</div>
        <select value={language} onChange={(e) => setLanguage(e.target.value)}>
          <option value="한국어">한국어</option>
          <option value="English">English</option>
        </select>

        <div className="sidebar-divider" />

        {/* Examples */}
        <div className="sidebar-section-title">📌 입력 예시</div>
        <div className="sidebar-examples">
          <ul>
            {examples.map((ex, i) => (
              <li key={i} onClick={() => { setTransaction(ex); navigateTo("journal"); }} style={{ cursor: "pointer" }}>
                • {ex}
              </li>
            ))}
          </ul>
        </div>

        <div className="sidebar-divider" />

        <div className="sidebar-tip">
          💡 Tip: 금액과 결제 방식을 포함하면 더 정확한 분개를 받을 수 있어요!
        </div>
      </aside>

      {/* ════════ MAIN CONTENT ════════ */}
      <main className="main-content">
        <div className="content-wrapper">

        {/* ──── PAGE: Journal Entry ──── */}
        {activePage === "journal" && (
          <>
            <div className="page-header">
              <h1>📊 분개 도우미</h1>
              <p>거래 내용을 입력하면 <strong>차변/대변 분개</strong>와 <strong>계정과목</strong>을 추천해드립니다.</p>
            </div>
            <div className="page-divider" />

            <div className="input-group">
              <label>거래 설명</label>
              <input
                type="text"
                placeholder="예: 사무용품 100,000원을 현금으로 구매"
                value={transaction}
                onChange={(e) => setTransaction(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleJournalSubmit()}
              />
            </div>
            <button className="submit-btn" onClick={handleJournalSubmit} disabled={loading}>
              {loading ? "생성 중..." : "🔍 분개 생성"}
            </button>

            {loading && (
              <div className="loading">
                <div className="spinner" />
                <span>GPT가 분개를 생성하고 있습니다...</span>
              </div>
            )}

            {result && (
              result.success ? (
                <>
                  <div className="result-card">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.content}</ReactMarkdown>
                  </div>
                  <div className="success-msg">✅ 분개가 생성되었습니다!</div>
                </>
              ) : (
                <div className="error-msg">⚠️ {result.error}</div>
              )
            )}
          </>
        )}

        {/* ──── PAGE: Term Explainer ──── */}
        {activePage === "term" && (
          <>
            <div className="page-header">
              <h1>📖 회계 용어 설명</h1>
              <p>회계 용어를 입력하면 <strong>한/영 설명</strong>과 <strong>분개 예시</strong>를 제공합니다.</p>
            </div>
            <div className="page-divider" />

            <div className="input-group">
              <label>회계 용어</label>
              <input
                type="text"
                placeholder="예: 감가상각, 매출채권, 이연법인세"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleTermSubmit()}
              />
            </div>
            <button className="submit-btn" onClick={handleTermSubmit} disabled={loading}>
              {loading ? "생성 중..." : "📖 용어 설명"}
            </button>

            {loading && (
              <div className="loading">
                <div className="spinner" />
                <span>GPT가 용어를 설명하고 있습니다...</span>
              </div>
            )}

            {result && (
              result.success ? (
                <>
                  <div className="result-card">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.content}</ReactMarkdown>
                  </div>
                  <div className="success-msg">✅ 용어 설명이 생성되었습니다!</div>
                </>
              ) : (
                <div className="error-msg">⚠️ {result.error}</div>
              )
            )}
          </>
        )}

        {/* ──── PAGE: History ──── */}
        {activePage === "history" && (
          <>
            <div className="page-header">
              <h1>📋 분개 히스토리</h1>
              <p>생성한 분개 기록입니다.</p>
            </div>
            <div className="page-divider" />

            {history.length === 0 ? (
              <div className="info-msg">아직 생성된 분개가 없습니다. 거래를 입력해보세요!</div>
            ) : (
              <>
                {history.map((item) => (
                  <div key={item.id} className="history-item">
                    <div
                      className="history-header"
                      onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                    >
                      <span>📄 {item.transaction}</span>
                      <span className="timestamp">{item.timestamp}</span>
                    </div>
                    {expandedId === item.id && (
                      <div className="history-body">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.content}</ReactMarkdown>
                      </div>
                    )}
                  </div>
                ))}

                <div className="page-divider" />
                <button className="clear-btn" onClick={handleClearHistory}>
                  🗑️ 히스토리 초기화
                </button>
              </>
            )}
          </>
        )}

        {/* ──── PAGE: File Analyzer ──── */}
        {activePage === "file" && (
          <>
            <div className="page-header">
              <h1>📁 파일 분석기</h1>
              <p>CSV, Excel, 또는 PDF 파일을 업로드하면 <strong>자동 정제</strong> 후 <strong>AI가 분석</strong>합니다.</p>
            </div>
            <div className="page-divider" />

            {/* File Upload */}
            <div className="input-group">
              <label>파일 선택 (CSV, Excel, PDF)</label>
              <div className="file-upload-area">
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.pdf"
                  onChange={handleFileUpload}
                />
                <p>파일을 선택하거나 여기에 드래그하세요</p>
              </div>
            </div>

            {/* Loading */}
            {fileLoading && (
              <div className="loading">
                <div className="spinner" />
                <span>파일을 분석하고 있습니다... pandas 정제 → GPT 분석 중</span>
              </div>
            )}

            {/* Error */}
            {fileError && (
              <div className="error-msg">⚠️ {fileError}</div>
            )}

            {/* Results */}
            {fileResult && (
              <>
                {/* Stats Cards */}
                <div className="success-msg">
                  ✅ {fileResult.filename} — {fileResult.row_count}건의 거래가 정제되었습니다.
                </div>

                <div className="stats-row">
                  <div className="stat-card stat-blue">
                    <div className="stat-number">{fileResult.row_count}</div>
                    <div className="stat-label">Transactions</div>
                  </div>
                  <div className="stat-card stat-green">
                    <div className="stat-number">{fileResult.columns.length}</div>
                    <div className="stat-label">Columns</div>
                  </div>
                  <div className={`stat-card ${fileResult.summary?.anomalies?.length > 0 ? "stat-red" : "stat-green"}`}>
                    <div className="stat-number">{fileResult.summary?.anomalies?.length || 0}</div>
                    <div className="stat-label">Anomalies</div>
                  </div>
                </div>

                {/* GPT Analysis */}
                {fileResult.gpt_analysis && (
                  <>
                    <h3 style={{ marginBottom: "8px", marginTop: "24px" }}>🤖 AI 분석 결과</h3>
                    <div className="result-card">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {fileResult.gpt_analysis}
                      </ReactMarkdown>
                    </div>
                  </>
                )}

                {/* Duplicate Vendors Warning */}
                {fileResult.summary?.duplicate_vendors?.length > 0 && (
                  <div className="warning-box">
                    <strong>⚠️ 중복 의심 거래처:</strong>
                    {fileResult.summary.duplicate_vendors.map((dup, i) => (
                      <div key={i} style={{ marginTop: "4px", fontSize: "14px" }}>
                        &quot;{dup.name_1}&quot; ↔ &quot;{dup.name_2}&quot; — {dup.issue}
                      </div>
                    ))}
                  </div>
                )}

                {/* Data Preview Table */}
                <h3 style={{ marginBottom: "8px", marginTop: "24px" }}>📋 데이터 미리보기 (상위 30건)</h3>
                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {fileResult.columns.map((col) => (
                          <th key={col}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {fileResult.preview.slice(0, 30).map((row, i) => (
                        <tr key={i}>
                          {fileResult.columns.map((col) => (
                            <td key={col}>
                              {col === "amount" || col === "balance"
                                ? (row[col] !== "" && row[col] !== null
                                    ? Number(row[col]).toLocaleString("en-US", { style: "currency", currency: "USD" })
                                    : "")
                                : (row[col] ?? "")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}

        {/* ──── Footer ──── */}
        <div className="footer">
          ⚠️ 이 앱은 학습 목적으로 만들어졌습니다. 실제 회계 처리 시에는 반드시 전문가와 상의하세요.
          <br />
          Frontend: Next.js | Backend: FastAPI | AI: OpenAI GPT-4o-mini
        </div>

        </div>
      </main>
    </div>
  );
}
