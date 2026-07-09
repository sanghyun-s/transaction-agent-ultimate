// components/tools/StatementReview.js
// First PREPARE add-on. Front end for the shared PDF service:
//   upload → /api/pdf/ingest → classified rows (included/excluded) + Source-A
//   reconciliation panel → Save to History.
import { useState } from "react";
import { API_BASE } from "../api";
import { t } from "../i18n";
import SaveToHistory from "../SaveToHistory";

const TYPE_LABEL = {
  vendor_payment: ["벤더 지급", "Vendor payment"],
  check_payment: ["수표", "Check"],
  check: ["수표", "Check"],
  deposit: ["입금", "Deposit"],
  payroll: ["급여", "Payroll"],
  transfer: ["이체", "Transfer"],
  bank_fee: ["은행 수수료", "Bank fee"],
  fee: ["수수료", "Fee"],
  interest: ["이자", "Interest"],
};

const money = (n) => Number(n || 0).toLocaleString("en-US", { style: "currency", currency: "USD" });

export default function StatementReview({ language }) {
  const [pdf, setPdf] = useState(null);
  const [engine, setEngine] = useState("rule");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const typeLabel = (ty) => {
    const p = TYPE_LABEL[ty];
    return p ? t(p[0], p[1], language) : ty;
  };

  const analyze = async () => {
    if (!pdf) return;
    setLoading(true); setResult(null); setError("");
    const fd = new FormData();
    fd.append("pdf_file", pdf);
    fd.append("engine", engine);
    fd.append("model", "sonnet");
    fd.append("source", "bank");
    try {
      const res = await fetch(`${API_BASE}/api/pdf/ingest`, { method: "POST", body: fd });
      const data = await res.json();
      if (!data.success) setError(data.error || t("분석 실패", "Analysis failed", language));
      else setResult(data);
    } catch {
      setError(t("백엔드에 연결할 수 없습니다.", "Cannot connect to backend.", language));
    }
    setLoading(false);
  };

  const recon = result?.reconciliation;
  const ec = result?.extraction_check;   // Source B — extraction completeness

  const historyMarkdown = () => {
    if (!result) return "";
    const L = [];
    L.push(`# ${t("명세서 검토", "Statement Review", language)} — ${result.filename || ""}`);
    if (result.metadata?.statement_period) L.push(`_${result.metadata.statement_period}_`);
    L.push("");
    L.push(`**${result.transactions.length} rows** — ${result.included_count} included / ${result.excluded_count} excluded. Included total ${money(result.included_total)}.`);
    if (recon?.available) {
      L.push("", "## Reconciliation");
      L.push(`- Beginning: ${money(recon.beginning_balance)}`);
      L.push(`- + Deposits: ${money(recon.total_deposits)}`);
      L.push(`- − Withdrawals: ${money(recon.total_withdrawals)}`);
      if (recon.checks) L.push(`- − Checks: ${money(recon.checks)}`);
      if (recon.transfers) L.push(`- − Transfers: ${money(recon.transfers)}`);
      if (recon.fees) L.push(`- − Fees: ${money(recon.fees)}`);
      L.push(`- = **Calculated ending: ${money(recon.calculated_ending)}**`);
      L.push(`- Reported ending: ${money(recon.reported_ending_balance)}`);
      L.push(`- Difference: ${money(recon.difference)} → ${recon.balanced ? "**Balanced ✓**" : "**Off ⚠**"}`);
    }
    if (ec && ec.status !== "unavailable") {
      L.push(`- Extraction check: ${ec.status === "complete" ? "**complete ✓**" : "**incomplete ⚠**"}${ec.lumped_debits ? " (lumped debits)" : ""}`);
    }
    L.push("", "## Transactions", "| Date | Description | Amount | Type | 1099 |", "|---|---|---|---|---|");
    result.transactions.forEach((r) => {
      L.push(`| ${r.date} | ${r.description} | ${money(r.amount)} | ${typeLabel(r.transaction_type)} | ${r.include_for_1099 ? "YES" : "NO"} |`);
    });
    return L.join("\n");
  };

  return (
    <>
      <div className="page-header">
        <h1>📄 {t("명세서 검토", "Statement Review", language)}</h1>
        <p>{t(
          "은행/카드 명세서를 업로드하면 각 거래를 분류하고, 명세서 자체 잔액이 맞는지 대사(reconciliation)합니다.",
          "Upload a bank/card statement: each row is classified, and the statement's own stated balance is reconciled.",
          language
        )}</p>
      </div>
      <div className="page-divider" />

      {/* Engine toggle */}
      <div className="input-group">
        <label>{t("분석 방식", "Analysis mode", language)}</label>
        <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem" }}>
          <button type="button" className="submit-btn" style={{ flex: 1, opacity: engine === "rule" ? 1 : 0.5 }} onClick={() => setEngine("rule")}>
            {t("빠른 미리보기 (무료)", "Quick preview (free)", language)}
          </button>
          <button type="button" className="submit-btn" style={{ flex: 1, opacity: engine === "skill" ? 1 : 0.5 }} onClick={() => setEngine("skill")}>
            {t("정밀 분석 (Skill · ~2분)", "Full analysis (Skill · ~2 min)", language)}
          </button>
        </div>
        <p style={{ fontSize: "0.8rem", color: "#666", marginTop: "0.4rem" }}>
          {engine === "skill"
            ? t("Claude PDF Skill이 컬럼을 정확히 읽고 대사 정보를 추출합니다. API 비용이 발생합니다.",
                "Claude PDF Skill reads the columns accurately and extracts the reconciliation. Uses API credits.", language)
            : t("규칙 기반 미리보기입니다. 대사(reconciliation)는 정밀 분석에서 제공됩니다.",
                "Rule-based preview. Reconciliation is available in Full analysis.", language)}
        </p>
      </div>

      {/* Upload */}
      <div className="input-group">
        <label>{t("명세서 (PDF) *", "Statement (PDF) *", language)}</label>
        <div className="file-upload-area">
          <input type="file" accept="application/pdf" onChange={(e) => setPdf(e.target.files[0] || null)} />
          <p>{pdf ? pdf.name : t("PDF 파일을 선택하세요", "Select a PDF file", language)}</p>
        </div>
      </div>

      <button className="submit-btn" onClick={analyze} disabled={loading || !pdf}>
        {loading ? t("분석 중...", "Analyzing...", language) : t("📄 명세서 분석", "📄 Analyze Statement", language)}
      </button>

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <span>
            {engine === "skill"
              ? t("Claude가 명세서를 읽고 있습니다 (1-4분)...", "Claude is reading the statement (1-4 min)...", language)
              : t("규칙 기반 분석 중...", "Running rule-based analysis...", language)}
          </span>
        </div>
      )}

      {error && <div className="error-msg">⚠️ {error}</div>}

      {result && (
        <>
          <div className="success-msg">
            ✅ {result.transactions.length} {t("행", "rows", language)} · {result.included_count} {t("포함", "included", language)} · {result.excluded_count} {t("제외", "excluded", language)} · {t("포함 합계", "included total", language)} {money(result.included_total)}
          </div>

          {/* Activity breakdown chips */}
          <div className="sr-chips">
            {Object.entries(result.breakdown || {}).map(([ty, n]) => (
              <span key={ty} className="sr-chip">{typeLabel(ty)} · {n}</span>
            ))}
          </div>

          {/* Reconciliation panel */}
          <h3 style={{ marginTop: "24px", marginBottom: "8px" }}>🧮 {t("명세서 대사", "Statement Reconciliation", language)}</h3>
          {recon?.available ? (
            <div className="sr-recon">
              <div className="sr-recon-row"><span /><span>{t("기초 잔액", "Beginning balance", language)}</span><span>{money(recon.beginning_balance)}</span></div>
              <div className="sr-recon-row"><span className="sr-op">+</span><span>{t("입금·수취", "Deposits & credits", language)}</span><span>{money(recon.total_deposits)}</span></div>
              <div className="sr-recon-row"><span className="sr-op">−</span><span>{t("출금", "Withdrawals", language)}</span><span>{money(recon.total_withdrawals)}</span></div>
              {recon.checks ? <div className="sr-recon-row"><span className="sr-op">−</span><span>{t("수표", "Checks", language)}</span><span>{money(recon.checks)}</span></div> : null}
              {recon.transfers ? <div className="sr-recon-row"><span className="sr-op">−</span><span>{t("이체", "Transfers", language)}</span><span>{money(recon.transfers)}</span></div> : null}
              {recon.fees ? <div className="sr-recon-row"><span className="sr-op">−</span><span>{t("수수료", "Fees & charges", language)}</span><span>{money(recon.fees)}</span></div> : null}
              <div className="sr-recon-row sr-recon-total"><span className="sr-op">=</span><span>{t("계산된 기말 잔액", "Calculated ending", language)}</span><span>{money(recon.calculated_ending)}</span></div>
              <div className="sr-recon-row"><span /><span>{t("명세서 기재 잔액", "Reported ending (as stated)", language)}</span><span>{money(recon.reported_ending_balance)}</span></div>
              <div className="sr-recon-row"><span /><span>{t("차이", "Difference", language)}</span><span>{money(recon.difference)}</span></div>
              <div className={`sr-verdict ${recon.balanced ? "sr-balanced" : "sr-off"}`}>
                {recon.balanced ? t("✓ 대사 일치", "✓ Balanced", language) : t(`⚠ ${money(recon.difference)} 불일치`, `⚠ Off by ${money(recon.difference)}`, language)}
              </div>
              {recon.notes && <p className="sr-notes">{recon.notes}</p>}
            </div>
          ) : (
            <div className="info-msg">{recon?.reason || t("정밀 분석(Skill)에서 대사가 제공됩니다.", "Reconciliation is available in Full (Skill) analysis.", language)}</div>
          )}

          {/* Extraction completeness (Source B) — low-key line under the reconciliation panel.
             Only shown on Skill runs where a stated summary exists to compare against. */}
          {ec && ec.status !== "unavailable" && (
            <div style={{ marginTop: "10px", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "6px",
                 color: ec.status === "complete" ? "#1a7f4b" : "#B26A00" }}>
              <span>{ec.status === "complete" ? "✓" : "⚠"}</span>
              <span>
                {ec.status === "complete"
                  ? t("추출 완결성: 추출된 행 합계가 명세서 기재 활동 합계와 일치합니다.",
                      "Extraction check: extracted rows sum to the statement's stated activity totals.", language)
                  : t("추출 완결성: 행 합계가 기재 합계와 일치하지 않습니다 — 누락·오분류 가능성이 있어 검토를 권장합니다.",
                      "Extraction check: rows don't sum to the stated totals — possible missed/miscounted rows, review suggested.", language)}
                {ec.lumped_debits ? t(" (단일 출금 합계 기준 비교)", " (compared against a single lumped-debits total)", language) : null}
              </span>
            </div>
          )}

          {/* Classified transactions */}
          <h3 style={{ marginTop: "24px", marginBottom: "8px" }}>📋 {t("거래 분류", "Row-level Classification", language)}</h3>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("날짜", "Date", language)}</th>
                  <th>{t("설명", "Description", language)}</th>
                  <th style={{ textAlign: "right" }}>{t("금액", "Amount", language)}</th>
                  <th>{t("유형", "Type", language)}</th>
                  <th style={{ textAlign: "center" }}>1099</th>
                  <th>{t("제외 사유", "Exclusion reason", language)}</th>
                </tr>
              </thead>
              <tbody>
                {result.transactions.map((r, i) => (
                  <tr key={i} className={r.include_for_1099 ? "" : "sr-excluded"}>
                    <td>{r.date}</td>
                    <td>{r.description}{r.review_required ? <span className="sr-flag" title="review">⚑</span> : null}</td>
                    <td style={{ textAlign: "right" }}>{money(r.amount)}</td>
                    <td>{typeLabel(r.transaction_type)}</td>
                    <td style={{ textAlign: "center" }}>{r.include_for_1099 ? "YES" : "NO"}</td>
                    <td style={{ fontSize: "0.85em", color: "#777" }}>{r.exclusion_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: "16px" }}>
            <SaveToHistory
              lang={language}
              payload={() => ({
                tool_name: "statement_review",
                title: result.filename || "statement",
                language,
                input_summary: `${result.included_count}/${result.transactions.length} included${recon?.available ? ` · recon ${recon.balanced ? "balanced" : "off"}` : ""}${ec && ec.status !== "unavailable" ? ` · extract ${ec.status}` : ""}`,
                output_content: historyMarkdown(),
                output_format: "markdown",
              })}
            />
          </div>
        </>
      )}
    </>
  );
}
