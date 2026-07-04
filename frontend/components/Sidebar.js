// components/Sidebar.js
import { LANGS, t } from "./i18n";

const EXAMPLES = [
  "사무용품 100,000원을 현금으로 구매",
  "거래처에 상품 500,000원을 외상으로 판매",
  "은행에서 1,000,000원을 대출받음",
  "직원 급여 3,000,000원을 보통예금에서 이체",
  "건물 임대료 200,000원을 현금으로 지급",
];

export default function Sidebar({ activePage, onNavigate, language, onLanguageChange, onExample }) {
  const nav = [
    { id: "journal", label: `📊 ${t("분개 도우미", "Journal Entry Generator", language)}` },
    { id: "term", label: `📖 ${t("용어 설명", "Term Explainer", language)}` },
    { id: "history", label: `📋 ${t("작업 기록", "Work History", language)}` },
    { id: "file", label: `📁 ${t("파일 분석기", "File Analyzer", language)}` },
    { id: "reconcile", label: `📑 ${t("1099 워크시트", "1099 Worksheet", language)}` },
    { id: "statement", label: `📄 ${t("명세서 검토", "Statement Review", language)}` },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-logo">📊</span>
        Transaction Agent
      </div>

      <nav className="sidebar-nav">
        {nav.map((n) => (
          <button
            key={n.id}
            className={`nav-item ${activePage === n.id ? "active" : ""}`}
            onClick={() => onNavigate(n.id)}
          >
            {n.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-divider" />

      {/* Global response-language selector */}
      <div className="sidebar-label">{t("응답 언어 선택", "Response language", language)}:</div>
      <select value={language} onChange={(e) => onLanguageChange(e.target.value)}>
        {LANGS.map((l) => (
          <option key={l} value={l}>{l}</option>
        ))}
      </select>

      <div className="sidebar-divider" />

      <div className="sidebar-section-title">📌 {t("입력 예시", "Examples", language)}</div>
      <div className="sidebar-examples">
        <ul>
          {EXAMPLES.map((ex, i) => (
            <li key={i} onClick={() => onExample(ex)} style={{ cursor: "pointer" }}>
              • {ex}
            </li>
          ))}
        </ul>
      </div>

      <div className="sidebar-divider" />

      <div className="sidebar-tip">
        💡 {t(
          "Tip: 금액과 결제 방식을 포함하면 더 정확한 분개를 받을 수 있어요!",
          "Tip: include the amount and payment method for a more accurate entry!",
          language
        )}
      </div>
    </aside>
  );
}
