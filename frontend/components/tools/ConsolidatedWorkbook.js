// components/tools/ConsolidatedWorkbook.js
// PREPARE Add-on 2 — the Excel generator. Minimal surface: upload statements,
// pick engine, build the 5-sheet master workbook, download it. All analysis
// lives in the workbook; the page shows only a single status line.
import { useState } from "react";
import { API_BASE } from "../api";
import { t } from "../i18n";
import SaveToHistory from "../SaveToHistory";

export default function ConsolidatedWorkbook({ language }) {
  const [pdfs, setPdfs] = useState([]);
  const [vendorCsv, setVendorCsv] = useState(null);
  const [engine, setEngine] = useState("skill"); // Skill is the default (accuracy)
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const build = async () => {
    if (!pdfs.length) return;
    setLoading(true); setResult(null); setError("");
    const fd = new FormData();
    pdfs.forEach((f) => fd.append("pdf_files", f));
    if (vendorCsv) fd.append("vendor_csv", vendorCsv);
    fd.append("engine", engine);
    fd.append("model", "sonnet");
    try {
      const res = await fetch(`${API_BASE}/api/consolidated/analyze`, { method: "POST", body: fd });
      const data = await res.json();
      if (!data.success) setError(data.error || t("생성 실패", "Build failed", language));
      else setResult(data);
    } catch {
      setError(t("백엔드에 연결할 수 없습니다.", "Cannot connect to backend.", language));
    }
    setLoading(false);
  };

  const downloadUrl = result?.excel_file_id
    ? `${API_BASE}/api/consolidated/download/${result.excel_file_id}`
    : null;

  const statusLine = result
    ? (() => {
        const n = result.statements_processed;
        const x = result.totals || {};
        return t(
          `명세서 ${n}건 · 벤더 ${x.vendor_count}곳 · $600 초과 ${x.over_threshold} · ${result.sheet_count}시트 워크북 준비됨`,
          `${n} statement${n > 1 ? "s" : ""} · ${x.vendor_count} vendors · ${x.over_threshold} over $600 · ${result.sheet_count}-sheet workbook ready`,
          language
        );
      })()
    : "";

  return (
    <>
      <div className="page-header">
        <h1>📘 {t("통합 워크북", "Consolidated Workbook", language)}</h1>
        <p>{t(
          "여러 명세서를 합쳐 회계사용 마스터 워크북(Excel)을 생성합니다.",
          "Combine multiple statements into an accountant-ready master workbook (Excel).",
          language
        )}</p>
      </div>
      <div className="page-divider" />

      <div className="input-group">
        <label>{t("분석 방식", "Analysis mode", language)}</label>
        <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
          <button type="button" className="submit-btn" style={{ flex: 1, opacity: engine === "skill" ? 1 : 0.5 }} onClick={() => setEngine("skill")}>
            {t("정밀 분석 (Skill · 권장)", "Full analysis (Skill · recommended)", language)}
          </button>
          <button type="button" className="submit-btn" style={{ flex: 1, opacity: engine === "rule" ? 1 : 0.5 }} onClick={() => setEngine("rule")}>
            {t("빠른 미리보기 (규칙)", "Quick preview (rule)", language)}
          </button>
        </div>
      </div>

      <div className="input-group">
        <label>{t("명세서 PDF (여러 개) *", "Statement PDFs (multiple) *", language)}</label>
        <div className="file-upload-area">
          <input type="file" accept="application/pdf" multiple onChange={(e) => setPdfs(Array.from(e.target.files || []))} />
          <p>{pdfs.length ? t(`${pdfs.length}개 선택됨`, `${pdfs.length} selected`, language) : t("PDF 여러 개를 선택하세요", "Select two or more PDFs", language)}</p>
        </div>
        {pdfs.length > 0 && (
          <p style={{ fontSize: "0.8rem", color: "#667085", marginTop: "0.3rem" }}>{pdfs.map((f) => f.name).join(" · ")}</p>
        )}
      </div>

      <div className="input-group">
        <label>{t("벤더 마스터 CSV (선택)", "Vendor master CSV (optional)", language)}</label>
        <div className="file-upload-area">
          <input type="file" accept=".csv" onChange={(e) => setVendorCsv((e.target.files && e.target.files[0]) || null)} />
          <p>{vendorCsv ? vendorCsv.name : t("표준 벤더명 목록 (첫 열)", "Canonical vendor names (first column)", language)}</p>
        </div>
      </div>

      <button className="submit-btn" onClick={build} disabled={loading || !pdfs.length}>
        {loading ? t("생성 중...", "Building...", language) : t("📘 워크북 생성", "📘 Build Workbook", language)}
      </button>

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <span>{engine === "skill"
            ? t(`Claude가 명세서 ${pdfs.length}건을 읽는 중입니다 (건당 1-4분)...`, `Claude is reading ${pdfs.length} statement(s) (1-4 min each)...`, language)
            : t("규칙 기반 분석 중...", "Running rule-based analysis...", language)}</span>
        </div>
      )}

      {error && <div className="error-msg">⚠️ {error}</div>}

      {result && (
        <>
          <div className="success-msg">✅ {statusLine}</div>

          {result.errors && result.errors.length > 0 && (
            <p style={{ fontSize: "0.85rem", color: "#B00020", marginTop: "8px" }}>
              {t("일부 명세서 처리 실패:", "Some statements failed:", language)} {result.errors.map((e) => e.file).join(", ")}
            </p>
          )}

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginTop: "14px", flexWrap: "wrap" }}>
            {downloadUrl && (
              <a className="submit-btn" style={{ textDecoration: "none", display: "inline-block" }} href={downloadUrl}>
                ⬇️ {t("워크북 다운로드 (.xlsx)", "Download workbook (.xlsx)", language)}
              </a>
            )}
            <SaveToHistory
              lang={language}
              payload={() => ({
                tool_name: "consolidated_workbook",
                title: t(`통합 워크북 — 명세서 ${result.statements_processed}건`, `Consolidated workbook — ${result.statements_processed} statements`, language),
                language,
                input_summary: `${result.statements_processed} stmts · ${(result.totals || {}).vendor_count} vendors · ${(result.totals || {}).over_threshold} over $600`,
                output_content: statusLine,
                output_format: "text",
              })}
            />
          </div>

          <p style={{ fontSize: "0.8rem", color: "#667085", marginTop: "10px" }}>
            {t(
              "상세 분석(벤더 롤업, 교차검증, 1099 판정)은 워크북 5개 시트에 있습니다.",
              "The full analysis — vendor rollup, cross-statement validation, and 1099 calls — is in the workbook's 5 sheets.",
              language
            )}
          </p>
        </>
      )}
    </>
  );
}
