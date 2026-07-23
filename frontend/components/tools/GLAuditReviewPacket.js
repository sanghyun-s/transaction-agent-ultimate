// components/tools/GLAuditReviewPacket.js
// LUCENT add-on (compact). Upload a company-level GL export -> a prioritized
// review queue, data-quality summary, top flagged rows, and a three-block
// evidence memo per row. Indicates review priority only — never concludes
// fraud or issues an audit opinion.
import { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE } from "../api";
import { t } from "../i18n";
import SaveToHistory from "../SaveToHistory";

const ENTITY_TYPES = ["Private company", "Public company", "Non-profit", "Fund"];
const SENSITIVITIES = ["Conservative (0.03)", "Balanced (0.05)", "Aggressive (0.10)"];

const TIER_STYLE = {
  High: { bg: "#FDECEA", fg: "#B3261E" },
  Medium: { bg: "#FEF4E5", fg: "#8A5300" },
  Low: { bg: "#F1EFE8", fg: "#5F5E5A" },
  Monitor: { bg: "#F1EFE8", fg: "#5F5E5A" },
};

const SIGNAL_GUIDE = [
  ["Unusual amount for account", "계정 대비 이례적 금액",
   "The amount is far from normal for this account.", "이 계정의 평소 규모와 크게 다릅니다."],
  ["Round number amount", "라운드 넘버 금액",
   "A clean figure with no cents — often an estimate or manual entry.", "센트 없는 정액 — 추정치나 수기 입력일 수 있습니다."],
  ["Weekend posting", "주말 전기",
   "Dated on a Saturday or Sunday, outside normal processing days.", "토·일에 기록되어 정상 처리일이 아닙니다."],
  ["Missing description", "적요 누락",
   "No memo text — a documentation gap in the audit trail.", "적요가 없어 감사증적이 약합니다."],
  ["New vendor", "신규 거래처",
   "A payee appearing rarely or for the first time.", "드물게 또는 처음 나타나는 거래처입니다."],
  ["Near approval threshold", "승인 한도 근접",
   "Just under a common approval limit — possible split purchase.", "승인 한도 바로 아래 — 분할 결제 가능성."],
  ["Co-occurrence", "복수 신호 중복",
   "Two or more signals on one row — this is what triggers escalation.", "한 거래에 신호 2개 이상 — 우선순위 상향의 근거."],
];

export default function GLAuditReviewPacket({ language }) {
  const [file, setFile] = useState(null);
  const [entityType, setEntityType] = useState("Private company");
  const [benchmark, setBenchmark] = useState(150000);
  const [sensitivity, setSensitivity] = useState("Balanced (0.05)");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [topN, setTopN] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [showGuide, setShowGuide] = useState(false);
  const fileRef = useRef(null);

  const fsPct = entityType === "Public company" ? 0.05 : 0.04;
  const fsMat = (Number(benchmark) || 0) * fsPct;
  const perfMat = fsMat * 0.5;
  const txnMat = fsMat * 0.8;
  const money = (n) => "$" + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
  const money2 = (n) => "$" + Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const run = async () => {
    if (!file) {
      setError(t("GL 파일을 먼저 선택하세요.", "Please choose a GL file first.", language));
      return;
    }
    setLoading(true); setError(""); setResult(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("entity_type", entityType);
    fd.append("benchmark", String(benchmark));
    fd.append("sensitivity", sensitivity);
    fd.append("period_start", periodStart);
    fd.append("period_end", periodEnd);
    fd.append("top_n", String(topN));
    fd.append("language", language);
    fd.append("generate_memos", "true");
    try {
      const res = await fetch(`${API_BASE}/api/gl-review/analyze`, { method: "POST", body: fd });
      const data = await res.json();
      if (!data.success) setError(data.error || t("분석 실패", "Analysis failed", language));
      else setResult(data);
    } catch {
      setError(t("백엔드에 연결할 수 없습니다.", "Cannot connect to backend.", language));
    }
    setLoading(false);
  };

  const cards = result?.summary_cards;
  const dq = cards?.data_quality || {};

  const historyMarkdown = () => {
    if (!result) return "";
    const L = [`# ${t("GL 감사 검토 패킷", "GL Audit Review Packet", language)}`, ""];
    L.push(`_${file?.name || ""}_`, "");
    L.push(`- ${t("분석 거래", "Transactions analyzed", language)}: ${cards?.transactions_analyzed}`);
    L.push(`- ${t("검토 대상", "Flagged for follow-up", language)}: ${cards?.flagged_for_follow_up}`);
    L.push(`- ${t("높음", "High", language)}: ${cards?.high_priority} · ${t("중간", "Medium", language)}: ${cards?.medium_priority}`, "");
    if (result.packet_memo) L.push(`## ${t("AI 검토 패킷", "AI Review Packet", language)}`, "", result.packet_memo, "");
    (result.row_memos || []).forEach((m, i) => {
      L.push(`### ${i + 1}. ${m.date} · ${m.vendor} · ${money2(m.amount)} (${m.priority})`, "", m.memo || "", "");
    });
    L.push("---", "", `_${result.guardrail || ""}_`);
    return L.join("\n");
  };

  return (
    <>
      <div className="page-header">
        <h1>🔍 {t("LUCENT — GL 감사 검토 패킷", "LUCENT — GL Audit Review Packet", language)}</h1>
        <p>{t(
          "회사 단위 GL을 업로드하면 우선 검토할 거래, 데이터 품질 점검, 요청할 증빙을 정리한 컴팩트 검토 패킷을 만듭니다.",
          "Upload a company-level GL export and generate a compact audit-review packet with priority signals, evidence requests, and downloadable results.",
          language)}</p>
      </div>
      <div className="page-divider" />

      {/* ---- Upload & Review Settings ---- */}
      <div className="form-section">
        <label className="form-label">{t("GL 파일 (CSV / Excel)", "GL file (CSV / Excel)", language)}</label>
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls"
          onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); setError(""); }} />
        {file && <div style={{ fontSize: "0.85rem", color: "#5F5E5A", marginTop: "6px" }}>{file.name}</div>}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "12px", marginTop: "14px" }}>
          <div>
            <label className="form-label">{t("법인 유형", "Entity type", language)}</label>
            <select value={entityType} onChange={(e) => setEntityType(e.target.value)}
              style={{ width: "100%", padding: "8px", borderRadius: "8px", border: "1px solid #D3D1C7" }}>
              {ENTITY_TYPES.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
          </div>
          <div>
            <label className="form-label">{t("기준 금액", "Benchmark amount", language)}</label>
            <input type="number" value={benchmark} min={0} step={10000}
              onChange={(e) => setBenchmark(e.target.value)}
              style={{ width: "100%", padding: "8px", borderRadius: "8px", border: "1px solid #D3D1C7" }} />
          </div>
          <div>
            <label className="form-label">{t("탐지 민감도", "Detection sensitivity", language)}</label>
            <select value={sensitivity} onChange={(e) => setSensitivity(e.target.value)}
              style={{ width: "100%", padding: "8px", borderRadius: "8px", border: "1px solid #D3D1C7" }}>
              {SENSITIVITIES.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
          </div>
          <div>
            <label className="form-label">{t("메모 건수", "Top memo count", language)}</label>
            <select value={topN} onChange={(e) => setTopN(Number(e.target.value))}
              style={{ width: "100%", padding: "8px", borderRadius: "8px", border: "1px solid #D3D1C7" }}>
              <option value={3}>Top 3</option>
              <option value={5}>Top 5</option>
            </select>
          </div>
          <div>
            <label className="form-label">{t("검토 시작일", "Period start", language)}</label>
            <input type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)}
              style={{ width: "100%", padding: "8px", borderRadius: "8px", border: "1px solid #D3D1C7" }} />
          </div>
          <div>
            <label className="form-label">{t("검토 종료일", "Period end", language)}</label>
            <input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
              style={{ width: "100%", padding: "8px", borderRadius: "8px", border: "1px solid #D3D1C7" }} />
          </div>
        </div>

        <div style={{ marginTop: "12px", fontSize: "0.85rem", color: "#5F5E5A" }}>
          {t("중요성 기준", "Materiality", language)}: FS {money(fsMat)} · {t("수행", "Performance", language)} {money(perfMat)} · {t("거래", "Transaction", language)} {money(txnMat)}
        </div>

        <button className="submit-btn" style={{ marginTop: "14px" }} onClick={run} disabled={loading || !file}>
          {loading ? t("검토 패킷 생성 중...", "Generating review packet...", language)
                   : t("검토 패킷 생성", "Generate Review Packet", language)}
        </button>
      </div>

      {error && <div className="error-msg" style={{ marginTop: "12px" }}>⚠️ {error}</div>}

      {result && (
        <>
          {/* ---- Summary cards ---- */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "12px", marginTop: "18px" }}>
            {[
              [t("분석 거래", "Transactions analyzed", language), cards.transactions_analyzed],
              [t("검토 대상", "Flagged for follow-up", language), cards.flagged_for_follow_up],
              [t("높은 우선순위", "High priority", language), cards.high_priority],
              [t("데이터 품질", "Data quality", language),
                `${dq.Pass || 0} ${t("통과", "pass", language)} · ${dq.Warning || 0} ${t("경고", "warn", language)}`],
            ].map(([label, val], i) => (
              <div key={i} style={{ border: "1px solid #E6E4DC", borderRadius: "10px", padding: "12px 14px", background: "#FCFBF8" }}>
                <div style={{ fontSize: "0.78rem", color: "#888780" }}>{label}</div>
                <div style={{ fontSize: "1.35rem", fontWeight: 600, color: "#1D3B6E", marginTop: "2px" }}>{val}</div>
              </div>
            ))}
          </div>

          {/* ---- AI Review Packet ---- */}
          {result.packet_memo && (
            <div style={{ marginTop: "18px", border: "1px solid #E6E4DC", borderRadius: "12px", padding: "16px 18px", background: "#FFFFFF" }}>
              <h3 style={{ marginTop: 0 }}>{t("AI 검토 패킷", "AI Review Packet", language)}</h3>
              <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.packet_memo}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* ---- Top flagged rows ---- */}
          {result.top_rows?.length > 0 && (
            <div style={{ marginTop: "18px" }}>
              <h3>{t(`상위 ${topN}건 검토 대상`, `Top ${topN} flagged rows`, language)}</h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }}>
                  <thead>
                    <tr style={{ background: "#F1EFE8" }}>
                      {[t("일자", "Date", language), t("계정", "Account", language),
                        t("거래처", "Vendor", language), t("금액", "Amount", language),
                        t("우선순위", "Priority", language), t("검토 신호", "Review signals", language)].map((h, i) => (
                        <th key={i} style={{ textAlign: i === 3 ? "right" : "left", padding: "8px 10px", borderBottom: "1px solid #D3D1C7" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.top_rows.map((r, i) => {
                      const st = TIER_STYLE[r.priority] || TIER_STYLE.Monitor;
                      return (
                        <tr key={i} style={{ borderBottom: "1px solid #EFEDE6" }}>
                          <td style={{ padding: "8px 10px", whiteSpace: "nowrap" }}>{r.date}</td>
                          <td style={{ padding: "8px 10px" }}>{r.account}</td>
                          <td style={{ padding: "8px 10px" }}>{r.vendor}</td>
                          <td style={{ padding: "8px 10px", textAlign: "right", whiteSpace: "nowrap" }}>{money2(r.amount)}</td>
                          <td style={{ padding: "8px 10px" }}>
                            <span style={{ padding: "2px 8px", borderRadius: "10px", background: st.bg, color: st.fg, fontSize: "0.78rem", fontWeight: 600 }}>
                              {r.priority}
                            </span>
                            {r.override && <span style={{ marginLeft: "6px", fontSize: "0.72rem", color: "#8A5300" }}>
                              {t("상향", "escalated", language)}</span>}
                          </td>
                          <td style={{ padding: "8px 10px", color: "#5F5E5A" }}>{r.signals}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ---- Row evidence memos ---- */}
          {result.row_memos?.length > 0 && (
            <div style={{ marginTop: "18px" }}>
              <h3>{t("증빙 요청 메모", "Evidence memos", language)}</h3>
              {result.row_memos.map((m, i) => {
                const st = TIER_STYLE[m.priority] || TIER_STYLE.Monitor;
                return (
                  <div key={i} style={{ border: "1px solid #E6E4DC", borderRadius: "12px", padding: "14px 16px", marginBottom: "10px", background: "#FCFBF8" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", marginBottom: "8px" }}>
                      <span style={{ padding: "2px 8px", borderRadius: "10px", background: st.bg, color: st.fg, fontSize: "0.75rem", fontWeight: 600 }}>{m.priority}</span>
                      <strong style={{ fontSize: "0.92rem" }}>{m.date} · {m.vendor} · {money2(m.amount)}</strong>
                    </div>
                    <div className="markdown-body" style={{ fontSize: "0.9rem" }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.memo || ""}</ReactMarkdown>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ---- Data quality detail ---- */}
          {result.integrity_findings?.length > 0 && (
            <details style={{ marginTop: "14px" }}>
              <summary style={{ cursor: "pointer", fontSize: "0.9rem", color: "#5F5E5A" }}>
                {t("데이터 품질 점검 상세", "Data quality check detail", language)}
              </summary>
              <ul style={{ fontSize: "0.87rem", color: "#5F5E5A", marginTop: "8px" }}>
                {result.integrity_findings.map((f, i) => (
                  <li key={i} style={{ marginBottom: "4px" }}>
                    <strong>{f.name}</strong> — {f.status}: {f.summary}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* ---- Exports ---- */}
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "18px", alignItems: "center" }}>
            {result.req_id && (
              <>
                <a className="submit-btn" style={{ width: "auto", padding: "9px 16px", textDecoration: "none", display: "inline-block" }}
                  href={`${API_BASE}/api/gl-review/download/${result.req_id}/csv`}>
                  {t("플래그 CSV 다운로드", "Download flagged CSV", language)}
                </a>
                <a className="submit-btn" style={{ width: "auto", padding: "9px 16px", textDecoration: "none", display: "inline-block" }}
                  href={`${API_BASE}/api/gl-review/download/${result.req_id}/memo`}>
                  {t("검토 메모 다운로드", "Download review memo", language)}
                </a>
              </>
            )}
            <SaveToHistory
              lang={language}
              payload={() => ({
                tool_name: "gl_audit_review_packet",
                title: `${t("GL 감사 검토 패킷", "GL Audit Review Packet", language)} — ${file?.name || ""}`,
                language,
                input_summary: `${cards?.transactions_analyzed} rows · ${cards?.flagged_for_follow_up} flagged · ${cards?.high_priority} high`,
                output_content: historyMarkdown(),
                output_format: "markdown",
              })}
            />
          </div>

          {/* ---- Guardrail ---- */}
          <div style={{ marginTop: "16px", fontSize: "0.82rem", color: "#888780", fontStyle: "italic" }}>
            {t("LUCENT는 검토 우선순위를 제시할 뿐, 부정이나 감사의견을 결론 내리지 않습니다.",
               "LUCENT indicates review priority only. It does not conclude fraud or issue audit opinions.",
               language)}
          </div>
        </>
      )}

      {/* ---- Mini signal guide ---- */}
      <div style={{ marginTop: "20px" }}>
        <button type="button" onClick={() => setShowGuide((s) => !s)}
          style={{ background: "none", border: "1px solid #D3D1C7", borderRadius: "8px", padding: "7px 12px", fontSize: "0.85rem", color: "#5F5E5A", cursor: "pointer" }}>
          {t("이 신호들은 무슨 뜻인가요?", "What do these signals mean?", language)}
        </button>
        {showGuide && (
          <div style={{ marginTop: "10px", border: "1px solid #E6E4DC", borderRadius: "12px", padding: "14px 16px", background: "#FCFBF8" }}>
            {SIGNAL_GUIDE.map(([en, ko, descEn, descKo], i) => (
              <div key={i} style={{ marginBottom: "10px" }}>
                <strong style={{ fontSize: "0.88rem" }}>{t(ko, en, language)}</strong>
                <div style={{ fontSize: "0.85rem", color: "#5F5E5A" }}>{t(descKo, descEn, language)}</div>
              </div>
            ))}
            <div style={{ fontSize: "0.8rem", color: "#888780", marginTop: "6px" }}>
              {t("각 신호는 확인이 필요하다는 표시일 뿐, 그 자체로 문제를 의미하지 않습니다.",
                 "Each signal is a prompt to look, not a finding in itself.", language)}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
