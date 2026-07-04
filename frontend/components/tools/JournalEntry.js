// components/tools/JournalEntry.js
import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE } from "../api";
import { t, apiLang } from "../i18n";
import LangOverride from "../LangOverride";
import SaveToHistory from "../SaveToHistory";

export default function JournalEntry({ language, preset }) {
  const [transaction, setTransaction] = useState("");
  const [override, setOverride] = useState("inherit");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // Apply an example clicked in the sidebar (preset.key changes each click).
  useEffect(() => {
    if (preset && preset.text) setTransaction(preset.text);
  }, [preset && preset.key]);

  const submit = async () => {
    if (!transaction.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/journal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transaction, language: apiLang(language, override) }),
      });
      setResult(await res.json());
    } catch {
      setResult({
        success: false,
        error: t(
          "백엔드 서버에 연결할 수 없습니다. FastAPI가 localhost:8000에서 실행 중인지 확인해주세요.",
          "Cannot connect to the backend. Is FastAPI running on localhost:8000?",
          language
        ),
      });
    }
    setLoading(false);
  };

  return (
    <>
      <div className="page-header">
        <h1>📊 {t("분개 도우미", "Journal Entry Generator", language)}</h1>
        <p>{t(
          "거래 내용을 입력하면 차변/대변 분개와 계정과목을 추천해드립니다.",
          "Describe a transaction and get the debit/credit journal entry with account titles.",
          language
        )}</p>
      </div>
      <div className="page-divider" />

      <LangOverride value={override} onChange={setOverride} lang={language} />

      <div className="input-group">
        <label>{t("거래 설명", "Transaction description", language)}</label>
        <input
          type="text"
          placeholder={t("예: 사무용품 100,000원을 현금으로 구매", "e.g. Purchased office supplies for $1,000 with cash", language)}
          value={transaction}
          onChange={(e) => setTransaction(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
      </div>
      <button className="submit-btn" onClick={submit} disabled={loading}>
        {loading ? t("생성 중...", "Generating...", language) : t("🔍 분개 생성", "🔍 Generate Entry", language)}
      </button>

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <span>{t("GPT가 분개를 생성하고 있습니다...", "GPT is generating the entry...", language)}</span>
        </div>
      )}

      {result && (
        result.success ? (
          <>
            <div className="result-card">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.content}</ReactMarkdown>
            </div>
            <div className="success-msg">✅ {t("분개가 생성되었습니다!", "Journal entry generated!", language)}</div>
            <SaveToHistory
              lang={language}
              payload={() => ({
                tool_name: "journal",
                title: transaction.slice(0, 120),
                language: apiLang(language, override),
                input_summary: transaction,
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
