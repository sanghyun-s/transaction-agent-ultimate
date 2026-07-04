// components/tools/Reconcile.js
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE } from "../api";
import { t } from "../i18n";
import SaveToHistory from "../SaveToHistory";

export default function Reconcile({ language }) {
  const [reconMode, setReconMode] = useState("rule-based");
  const [reconModel, setReconModel] = useState("claude-haiku-4-5-20251001");
  const [reconPdf, setReconPdf] = useState(null);
  const [reconCsv, setReconCsv] = useState(null);
  const [reconLoading, setReconLoading] = useState(false);
  const [reconResult, setReconResult] = useState(null);
  const [reconError, setReconError] = useState("");

  const submit = async () => {
    if (!reconPdf) return;
    setReconLoading(true);
    setReconResult(null);
    setReconError("");
    const fd = new FormData();
    fd.append("pdf_file", reconPdf);
    if (reconCsv) fd.append("vendor_list", reconCsv);
    if (reconMode === "agent") fd.append("model", reconModel);
    const endpoint = reconMode === "agent"
      ? `${API_BASE}/api/reconcile/agent`
      : `${API_BASE}/api/reconcile/rule-based`;
    try {
      const res = await fetch(endpoint, { method: "POST", body: fd });
      const data = await res.json();
      if (!data.success) setReconError(data.error || t("처리 실패", "Processing failed", language));
      else setReconResult(data);
    } catch {
      setReconError(t("백엔드 서버에 연결할 수 없습니다.", "Cannot connect to backend server.", language));
    }
    setReconLoading(false);
  };

  // Text stored to Work History (the Excel stays downloadable on this page).
  const historyText = (r) => {
    const lines = [
      `# 1099 Reconciliation — ${reconPdf ? reconPdf.name : ""}`,
      "",
      `- Transactions: ${r.transaction_count}`,
      `- Vendors: ${r.vendor_count}`,
      `- Total: $${Number(r.total_amount).toLocaleString("en-US")}`,
      `- Over $600: ${r.vendors_over_600}`,
      `- Need review: ${r.vendors_needing_review}`,
    ];
    if (r.agent_summary) lines.push("", "## Agent summary", r.agent_summary);
    return lines.join("\n");
  };

  return (
    <>
      <div className="page-header">
        <h1>📑 {t("1099 정산 워크시트", "1099 Pre-Reconciliation Worksheet", language)}</h1>
        <p>{t(
          "은행/카드 명세서를 업로드하면 벤더별 지급 내역과 1099 대상을 자동 추출하여 회계사용 엑셀 파일을 생성합니다.",
          "Upload a bank or credit card statement to extract and aggregate vendor payments into an accountant-grade Excel workbook for 1099 prep.",
          language
        )}</p>
      </div>
      <div className="page-divider" />

      {/* Mode toggle */}
      <div className="input-group">
        <label>{t("처리 방식", "Processing Mode", language)}</label>
        <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
          <button type="button" className="submit-btn" style={{ flex: 1, opacity: reconMode === "rule-based" ? 1 : 0.5 }} onClick={() => setReconMode("rule-based")}>
            {t("규칙 기반 (무료)", "Rule-Based (Free)", language)}
          </button>
          <button type="button" className="submit-btn" style={{ flex: 1, opacity: reconMode === "agent" ? 1 : 0.5 }} onClick={() => setReconMode("agent")}>
            {t("Claude 에이전트 (API 사용)", "Claude Agent (Uses API)", language)}
          </button>
        </div>
      </div>

      {reconMode === "agent" && (
        <div className="input-group">
          <label>{t("모델 선택", "Agent Model", language)}</label>
          <select value={reconModel} onChange={(e) => setReconModel(e.target.value)} style={{ padding: "0.5rem", width: "100%" }}>
            <option value="claude-haiku-4-5-20251001">
              Claude Haiku 4.5 — {t("저렴/빠름 (~$0.01)", "cheap/fast (~$0.01/run)", language)}
            </option>
            <option value="claude-opus-4-7">
              Claude Opus 4.7 — {t("고품질 (~$0.09)", "high quality (~$0.09/run)", language)}
            </option>
          </select>
        </div>
      )}

      {/* PDF upload */}
      <div className="input-group">
        <label>{t("은행/카드 명세서 (PDF) *", "Bank / Credit Card Statement (PDF) *", language)}</label>
        <div className="file-upload-area">
          <input type="file" accept="application/pdf" onChange={(e) => setReconPdf(e.target.files[0] || null)} />
          <p>{reconPdf ? reconPdf.name : t("PDF 파일을 선택하세요", "Select a PDF file", language)}</p>
        </div>
      </div>

      {/* Vendor list upload (optional) */}
      <div className="input-group">
        <label>{t("벤더 목록 (CSV, 선택사항)", "Known Vendor List (CSV, optional)", language)}</label>
        <div className="file-upload-area">
          <input type="file" accept=".csv" onChange={(e) => setReconCsv(e.target.files[0] || null)} />
          <p>{reconCsv ? reconCsv.name : t("CSV 파일을 선택하세요 (선택사항)", "Select a CSV file (optional)", language)}</p>
        </div>
      </div>

      <button className="submit-btn" onClick={submit} disabled={reconLoading || !reconPdf}>
        {reconLoading ? t("처리 중...", "Processing...", language) : t("📄 명세서 처리", "📄 Process Statement", language)}
      </button>

      {reconLoading && (
        <div className="loading">
          <div className="spinner" />
          <span>
            {reconMode === "agent"
              ? t("Claude 에이전트가 작업 중입니다 (10-30초)...", "Claude agent is working (10-30s)...", language)
              : t("규칙 기반 파이프라인 실행 중...", "Running rule-based pipeline...", language)}
          </span>
        </div>
      )}

      {reconError && <div className="error-msg">⚠️ {reconError}</div>}

      {reconResult && (
        <>
          <div className="success-msg">
            ✅ {t(
              `${reconResult.transaction_count}건의 거래가 ${reconResult.vendor_count}개 벤더로 정산되었습니다.`,
              `${reconResult.transaction_count} transactions reconciled into ${reconResult.vendor_count} vendors.`,
              language
            )}
          </div>

          <div className="stats-row">
            <div className="stat-card stat-blue">
              <div className="stat-number">{reconResult.transaction_count}</div>
              <div className="stat-label">{t("거래 건수", "Transactions", language)}</div>
            </div>
            <div className="stat-card stat-blue">
              <div className="stat-number">{reconResult.vendor_count}</div>
              <div className="stat-label">{t("벤더 수", "Vendors", language)}</div>
            </div>
            <div className="stat-card stat-green">
              <div className="stat-number">${Number(reconResult.total_amount).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
              <div className="stat-label">{t("총 금액", "Total", language)}</div>
            </div>
            <div className={`stat-card ${reconResult.vendors_over_600 > 0 ? "stat-red" : "stat-green"}`}>
              <div className="stat-number">{reconResult.vendors_over_600}</div>
              <div className="stat-label">{t("$600 초과", "Over $600", language)}</div>
            </div>
            <div className={`stat-card ${reconResult.vendors_needing_review > 0 ? "stat-red" : "stat-green"}`}>
              <div className="stat-number">{reconResult.vendors_needing_review}</div>
              <div className="stat-label">{t("검토 필요", "Need Review", language)}</div>
            </div>
          </div>

          {reconResult.mode === "agent" && (
            <div className="stats-row">
              <div className="stat-card stat-blue">
                <div className="stat-number">{reconResult.agent_tool_calls}</div>
                <div className="stat-label">{t("에이전트 도구 호출", "Tool Calls", language)}</div>
              </div>
              <div className="stat-card stat-blue">
                <div className="stat-number">${Number(reconResult.agent_cost_usd).toFixed(4)}</div>
                <div className="stat-label">{t("API 비용", "API Cost", language)}</div>
              </div>
            </div>
          )}

          {reconResult.agent_summary && (
            <>
              <h3 style={{ marginBottom: "8px", marginTop: "24px" }}>🤖 {t("에이전트 분석", "Agent Analysis", language)}</h3>
              <div className="result-card">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{reconResult.agent_summary}</ReactMarkdown>
              </div>
            </>
          )}

          <h3 style={{ marginBottom: "8px", marginTop: "24px" }}>{t("📋 벤더 요약 (상위 10개)", "📋 Vendor Summary (Top 10)", language)}</h3>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("벤더", "Vendor", language)}</th>
                  <th>{t("유형", "Entity", language)}</th>
                  <th style={{ textAlign: "right" }}>{t("총액", "Total", language)}</th>
                  <th style={{ textAlign: "center" }}>{t("건수", "# Pmts", language)}</th>
                  <th style={{ textAlign: "center" }}>{t("카테고리", "Category", language)}</th>
                  <th style={{ textAlign: "center" }}>{t("신뢰도", "Confidence", language)}</th>
                  <th style={{ textAlign: "center" }}>{t("상태", "Status", language)}</th>
                </tr>
              </thead>
              <tbody>
                {reconResult.vendor_preview.slice(0, 10).map((v, i) => (
                  <tr key={i} style={{ backgroundColor: v.review ? "#FFF4CC" : "transparent" }}>
                    <td>{v.name}</td>
                    <td>{v.entity}</td>
                    <td style={{ textAlign: "right" }}>${Number(v.total).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
                    <td style={{ textAlign: "center" }}>{v.count}</td>
                    <td style={{ textAlign: "center" }}>{v.category}</td>
                    <td style={{ textAlign: "center" }}>{Math.round((v.confidence || 0) * 100)}%</td>
                    <td style={{ textAlign: "center" }}>{v.review ? t("⚠️ 검토", "⚠️ Review", language) : t("✓ 정상", "✓ OK", language)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: "24px", display: "flex", gap: "12px", flexWrap: "wrap" }}>
            <a
              href={`${API_BASE}/api/reconcile/download/${reconResult.file_id}`}
              download="vendor_reconciliation.xlsx"
              className="submit-btn"
              style={{ textDecoration: "none", display: "inline-block", textAlign: "center" }}
            >
              {t("Excel 다운로드", "Download Excel", language)}
            </a>
            <SaveToHistory
              lang={language}
              payload={() => ({
                tool_name: "reconcile",
                title: reconPdf ? reconPdf.name : "1099 worksheet",
                language,
                input_summary: `${reconResult.transaction_count} txns · ${reconResult.vendor_count} vendors`,
                output_content: historyText(reconResult),
                output_format: "markdown",
              })}
            />
          </div>
        </>
      )}
    </>
  );
}
