// pages/index.js
// ============================================================
// SOTA Next.js Frontend — All 5 pages with sidebar
// ============================================================
// - Page 1: Journal Entry (분개 도우미)
// - Page 2: Term Explainer (용어 설명)
// - Page 3: History (분개 히스토리)
// - Page 4: File Analyzer (파일 분석기) — CSV, Excel, PDF
// - Page 5: 1099 Reconciliation (1099 정산 워크시트) — Rule-Based + Claude Agent SDK
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

  // ── Reconciliation state (Session 3 add-on) ──
  const [reconMode, setReconMode] = useState("rule-based");
  const [reconModel, setReconModel] = useState("claude-haiku-4-5-20251001");
  const [reconPdf, setReconPdf] = useState(null);
  const [reconCsv, setReconCsv] = useState(null);
  const [reconLoading, setReconLoading] = useState(false);
  const [reconResult, setReconResult] = useState(null);
  const [reconError, setReconError] = useState("");

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

  // ── API call: Reconciliation ──
  const handleReconSubmit = async () => {
    if (!reconPdf) return;
    setReconLoading(true);
    setReconResult(null);
    setReconError("");

    const fd = new FormData();
    fd.append("pdf_file", reconPdf);
    if (reconCsv) fd.append("vendor_list", reconCsv);
    if (reconMode === "agent") fd.append("model", reconModel);

    const endpoint =
      reconMode === "agent"
        ? `${API_BASE}/api/reconcile/agent`
        : `${API_BASE}/api/reconcile/rule-based`;

    try {
      const res = await fetch(endpoint, { method: "POST", body: fd });
      const data = await res.json();
      if (!data.success) {
        setReconError(data.error || "Processing failed");
      } else {
        setReconResult(data);
      }
    } catch (err) {
      setReconError(
        language === "한국어"
          ? "백엔드 서버에 연결할 수 없습니다."
          : "Cannot connect to backend server."
      );
    }
    setReconLoading(false);
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
          <button className={`nav-item ${activePage === "reconcile" ? "active" : ""}`} onClick={() => navigateTo("reconcile")}>
            📑 {language === "한국어" ? "1099 정산 워크시트" : "1099 Reconciliation"}
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

        {/* ──── PAGE: 1099 Reconciliation (Session 3 Add-On) ──── */}
        {activePage === "reconcile" && (
          <>
            <div className="page-header">
              <h1>
                📑 {language === "한국어" ? "1099 정산 워크시트" : "1099 Pre-Reconciliation Worksheet"}
              </h1>
              <p>
                {language === "한국어" ? (
                  <>은행/카드 명세서를 업로드하면 <strong>벤더별 지급 내역</strong>과 <strong>1099 대상</strong>을 자동 추출하여 회계사용 엑셀 파일을 생성합니다.</>
                ) : (
                  <>Upload a bank or credit card statement to extract, normalize, and aggregate <strong>vendor payments</strong> — producing an accountant-grade Excel workbook for <strong>1099 preparation</strong>.</>
                )}
              </p>
            </div>
            <div className="page-divider" />

            {/* Mode toggle */}
            <div className="input-group">
              <label>{language === "한국어" ? "처리 방식" : "Processing Mode"}</label>
              <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  className="submit-btn"
                  style={{
                    flex: 1,
                    opacity: reconMode === "rule-based" ? 1 : 0.5,
                  }}
                  onClick={() => setReconMode("rule-based")}
                >
                  {language === "한국어" ? "규칙 기반 (무료)" : "Rule-Based (Free)"}
                </button>
                <button
                  type="button"
                  className="submit-btn"
                  style={{
                    flex: 1,
                    opacity: reconMode === "agent" ? 1 : 0.5,
                  }}
                  onClick={() => setReconMode("agent")}
                >
                  {language === "한국어" ? "Claude 에이전트 (API 사용)" : "Claude Agent (Uses API)"}
                </button>
              </div>
            </div>

            {reconMode === "agent" && (
              <div className="input-group">
                <label>{language === "한국어" ? "모델 선택" : "Agent Model"}</label>
                <select
                  value={reconModel}
                  onChange={(e) => setReconModel(e.target.value)}
                  style={{ padding: "0.5rem", width: "100%" }}
                >
                  <option value="claude-haiku-4-5-20251001">
                    Claude Haiku 4.5 — {language === "한국어" ? "저렴/빠름 (~$0.01)" : "cheap/fast (~$0.01/run)"}
                  </option>
                  <option value="claude-opus-4-7">
                    Claude Opus 4.7 — {language === "한국어" ? "고품질 (~$0.09)" : "high quality (~$0.09/run)"}
                  </option>
                </select>
              </div>
            )}

            {/* PDF upload */}
            <div className="input-group">
              <label>
                {language === "한국어" ? "은행/카드 명세서 (PDF) *" : "Bank / Credit Card Statement (PDF) *"}
              </label>
              <div className="file-upload-area">
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setReconPdf(e.target.files[0] || null)}
                />
                <p>{reconPdf ? reconPdf.name : (language === "한국어" ? "PDF 파일을 선택하세요" : "Select a PDF file")}</p>
              </div>
            </div>

            {/* Vendor list upload (optional) */}
            <div className="input-group">
              <label>
                {language === "한국어" ? "벤더 목록 (CSV, 선택사항)" : "Known Vendor List (CSV, optional)"}
              </label>
              <div className="file-upload-area">
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setReconCsv(e.target.files[0] || null)}
                />
                <p>{reconCsv ? reconCsv.name : (language === "한국어" ? "CSV 파일을 선택하세요 (선택사항)" : "Select a CSV file (optional)")}</p>
              </div>
            </div>

            <button
              className="submit-btn"
              onClick={handleReconSubmit}
              disabled={reconLoading || !reconPdf}
            >
              {reconLoading
                ? (language === "한국어" ? "처리 중..." : "Processing...")
                : (language === "한국어" ? "📄 명세서 처리" : "📄 Process Statement")}
            </button>

            {reconLoading && (
              <div className="loading">
                <div className="spinner" />
                <span>
                  {reconMode === "agent"
                    ? (language === "한국어" ? "Claude 에이전트가 작업 중입니다 (10-30초)..." : "Claude agent is working (10-30s)...")
                    : (language === "한국어" ? "규칙 기반 파이프라인 실행 중..." : "Running rule-based pipeline...")}
                </span>
              </div>
            )}

            {reconError && (
              <div className="error-msg">⚠️ {reconError}</div>
            )}

            {reconResult && (
              <>
                <div className="success-msg">
                  ✅ {language === "한국어"
                    ? `${reconResult.transaction_count}건의 거래가 ${reconResult.vendor_count}개 벤더로 정산되었습니다.`
                    : `${reconResult.transaction_count} transactions reconciled into ${reconResult.vendor_count} vendors.`}
                </div>

                <div className="stats-row">
                  <div className="stat-card stat-blue">
                    <div className="stat-number">{reconResult.transaction_count}</div>
                    <div className="stat-label">{language === "한국어" ? "거래 건수" : "Transactions"}</div>
                  </div>
                  <div className="stat-card stat-blue">
                    <div className="stat-number">{reconResult.vendor_count}</div>
                    <div className="stat-label">{language === "한국어" ? "벤더 수" : "Vendors"}</div>
                  </div>
                  <div className="stat-card stat-green">
                    <div className="stat-number">${Number(reconResult.total_amount).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
                    <div className="stat-label">{language === "한국어" ? "총 금액" : "Total"}</div>
                  </div>
                  <div className={`stat-card ${reconResult.vendors_over_600 > 0 ? "stat-red" : "stat-green"}`}>
                    <div className="stat-number">{reconResult.vendors_over_600}</div>
                    <div className="stat-label">{language === "한국어" ? "$600 초과" : "Over $600"}</div>
                  </div>
                  <div className={`stat-card ${reconResult.vendors_needing_review > 0 ? "stat-red" : "stat-green"}`}>
                    <div className="stat-number">{reconResult.vendors_needing_review}</div>
                    <div className="stat-label">{language === "한국어" ? "검토 필요" : "Need Review"}</div>
                  </div>
                </div>

                {reconResult.mode === "agent" && (
                  <div className="stats-row">
                    <div className="stat-card stat-blue">
                      <div className="stat-number">{reconResult.agent_tool_calls}</div>
                      <div className="stat-label">{language === "한국어" ? "에이전트 도구 호출" : "Tool Calls"}</div>
                    </div>
                    <div className="stat-card stat-blue">
                      <div className="stat-number">${Number(reconResult.agent_cost_usd).toFixed(4)}</div>
                      <div className="stat-label">{language === "한국어" ? "API 비용" : "API Cost"}</div>
                    </div>
                  </div>
                )}

                {reconResult.agent_summary && (
                  <>
                    <h3 style={{ marginBottom: "8px", marginTop: "24px" }}>
                      🤖 {language === "한국어" ? "에이전트 분석" : "Agent Analysis"}
                    </h3>
                    <div className="result-card">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {reconResult.agent_summary}
                      </ReactMarkdown>
                    </div>
                  </>
                )}

                <h3 style={{ marginBottom: "8px", marginTop: "24px" }}>
                  {language === "한국어" ? "📋 벤더 요약 (상위 10개)" : "📋 Vendor Summary (Top 10)"}
                </h3>
                <div className="table-wrapper">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{language === "한국어" ? "벤더" : "Vendor"}</th>
                        <th>{language === "한국어" ? "유형" : "Entity"}</th>
                        <th style={{ textAlign: "right" }}>{language === "한국어" ? "총액" : "Total"}</th>
                        <th style={{ textAlign: "center" }}>{language === "한국어" ? "건수" : "# Pmts"}</th>
                        <th style={{ textAlign: "center" }}>{language === "한국어" ? "카테고리" : "Category"}</th>
                        <th style={{ textAlign: "center" }}>{language === "한국어" ? "신뢰도" : "Confidence"}</th>
                        <th style={{ textAlign: "center" }}>{language === "한국어" ? "상태" : "Status"}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reconResult.vendor_preview.slice(0, 10).map((v, i) => (
                        <tr key={i} style={{ backgroundColor: v.review ? "#FFF4CC" : "transparent" }}>
                          <td>{v.name}</td>
                          <td>{v.entity}</td>
                          <td style={{ textAlign: "right" }}>
                            ${Number(v.total).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                          </td>
                          <td style={{ textAlign: "center" }}>{v.count}</td>
                          <td style={{ textAlign: "center" }}>{v.category}</td>
                          <td style={{ textAlign: "center" }}>{Math.round((v.confidence || 0) * 100)}%</td>
                          <td style={{ textAlign: "center" }}>
                            {v.review
                              ? (language === "한국어" ? "⚠️ 검토" : "⚠️ Review")
                              : (language === "한국어" ? "✓ 정상" : "✓ OK")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div style={{ marginTop: "24px" }}>
                  <a
                    href={`${API_BASE}/api/reconcile/download/${reconResult.file_id}`}
                    download="vendor_reconciliation.xlsx"
                    className="submit-btn"
                    style={{ textDecoration: "none", display: "inline-block", textAlign: "center" }}
                  >
                    {language === "한국어" ? "Excel 다운로드" : "Download Excel"}
                  </a>
                </div>
              </>
            )}
          </>
        )}

        {/* ──── Footer ──── */}
        <div className="footer">
          ⚠️ 이 앱은 학습 목적으로 만들어졌습니다. 실제 회계 처리 시에는 반드시 전문가와 상의하세요.
          <br />
          Frontend: Next.js | Backend: FastAPI | AI: OpenAI GPT-4o-mini + Claude Agent SDK
        </div>

        </div>
      </main>
    </div>
  );
}