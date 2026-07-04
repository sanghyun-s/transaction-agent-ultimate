// components/tools/TermExplainer.js
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE } from "../api";
import { t, apiLang } from "../i18n";
import LangOverride from "../LangOverride";
import SaveToHistory from "../SaveToHistory";

export default function TermExplainer({ language }) {
  const [term, setTerm] = useState("");
  const [override, setOverride] = useState("inherit");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!term.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/term`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ term, language: apiLang(language, override) }),
      });
      setResult(await res.json());
    } catch {
      setResult({
        success: false,
        error: t("백엔드 서버에 연결할 수 없습니다.", "Cannot connect to the backend server.", language),
      });
    }
    setLoading(false);
  };

  return (
    <>
      <div className="page-header">
        <h1>📖 {t("회계 용어 설명", "Term Explainer", language)}</h1>
        <p>{t(
          "회계 용어를 입력하면 한/영 설명과 분개 예시를 제공합니다.",
          "Enter an accounting term for a Korean/English explanation and a journal-entry example.",
          language
        )}</p>
      </div>
      <div className="page-divider" />

      <LangOverride value={override} onChange={setOverride} lang={language} />

      <div className="input-group">
        <label>{t("회계 용어", "Accounting term", language)}</label>
        <input
          type="text"
          placeholder={t("예: 감가상각, 매출채권, 이연법인세", "e.g. depreciation, accounts receivable", language)}
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
      </div>
      <button className="submit-btn" onClick={submit} disabled={loading}>
        {loading ? t("생성 중...", "Generating...", language) : t("📖 용어 설명", "📖 Explain Term", language)}
      </button>

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <span>{t("GPT가 용어를 설명하고 있습니다...", "GPT is explaining the term...", language)}</span>
        </div>
      )}

      {result && (
        result.success ? (
          <>
            <div className="result-card">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.content}</ReactMarkdown>
            </div>
            <div className="success-msg">✅ {t("용어 설명이 생성되었습니다!", "Explanation generated!", language)}</div>
            <SaveToHistory
              lang={language}
              payload={() => ({
                tool_name: "term",
                title: term.slice(0, 120),
                language: apiLang(language, override),
                input_summary: term,
                output_content: result.content,
                output_format: "markdown",
              })}
            />
          </>
        ) : (
          <div className="error-msg">⚠️ {result.error}</div>
        )
      )}
    </>
  );
}
