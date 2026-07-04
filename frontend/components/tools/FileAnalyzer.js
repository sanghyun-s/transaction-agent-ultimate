// components/tools/FileAnalyzer.js
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE } from "../api";
import { t } from "../i18n";
import SaveToHistory from "../SaveToHistory";

export default function FileAnalyzer({ language }) {
  const [fileResult, setFileResult] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState("");

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setFileLoading(true);
    setFileError("");
    setFileResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/api/analyze-file`, { method: "POST", body: formData });
      const data = await res.json();
      if (data.success) setFileResult(data);
      else setFileError(data.error || t("파일 처리에 실패했습니다.", "File processing failed.", language));
    } catch {
      setFileError(t("네트워크 오류 — 백엔드가 8000 포트에서 실행 중인가요?", "Network error — is the backend running on port 8000?", language));
    } finally {
      setFileLoading(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>📁 {t("파일 분석기", "File Analyzer", language)}</h1>
        <p>{t(
          "CSV, Excel, 또는 PDF 파일을 업로드하면 자동 정제 후 AI가 분석합니다.",
          "Upload a CSV, Excel, or PDF file — it's auto-cleaned and analyzed by AI.",
          language
        )}</p>
      </div>
      <div className="page-divider" />

      <div className="input-group">
        <label>{t("파일 선택 (CSV, Excel, PDF)", "Choose a file (CSV, Excel, PDF)", language)}</label>
        <div className="file-upload-area">
          <input type="file" accept=".csv,.xlsx,.xls,.pdf" onChange={handleFileUpload} />
          <p>{t("파일을 선택하거나 여기에 드래그하세요", "Select a file or drag it here", language)}</p>
        </div>
      </div>

      {fileLoading && (
        <div className="loading">
          <div className="spinner" />
          <span>{t("파일을 분석하고 있습니다... pandas 정제 → GPT 분석 중", "Analyzing... pandas cleaning → GPT analysis", language)}</span>
        </div>
      )}

      {fileError && <div className="error-msg">⚠️ {fileError}</div>}

      {fileResult && (
        <>
          <div className="success-msg">
            ✅ {fileResult.filename} — {t(
              `${fileResult.row_count}건의 거래가 정제되었습니다.`,
              `${fileResult.row_count} rows cleaned.`,
              language
            )}
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

          {fileResult.gpt_analysis && (
            <>
              <h3 style={{ marginBottom: "8px", marginTop: "24px" }}>🤖 {t("AI 분석 결과", "AI Analysis", language)}</h3>
              <div className="result-card">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{fileResult.gpt_analysis}</ReactMarkdown>
              </div>
              <SaveToHistory
                lang={language}
                payload={() => ({
                  tool_name: "file_analyzer",
                  title: fileResult.filename,
                  language,
                  input_summary: `${fileResult.filename} · ${fileResult.row_count} rows`,
                  output_content: fileResult.gpt_analysis,
                  output_format: "markdown",
                  file_type: (fileResult.filename.split(".").pop() || "").toLowerCase(),
                })}
              />
            </>
          )}

          {fileResult.summary?.duplicate_vendors?.length > 0 && (
            <div className="warning-box">
              <strong>⚠️ {t("중복 의심 거래처:", "Possible duplicate vendors:", language)}</strong>
              {fileResult.summary.duplicate_vendors.map((dup, i) => (
                <div key={i} style={{ marginTop: "4px", fontSize: "14px" }}>
                  &quot;{dup.name_1}&quot; ↔ &quot;{dup.name_2}&quot; — {dup.issue}
                </div>
              ))}
            </div>
          )}

          <h3 style={{ marginBottom: "8px", marginTop: "24px" }}>📋 {t("데이터 미리보기 (상위 30건)", "Data preview (first 30)", language)}</h3>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>{fileResult.columns.map((col) => <th key={col}>{col}</th>)}</tr>
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
  );
}
