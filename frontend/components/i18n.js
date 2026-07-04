// components/i18n.js
// ============================================================
// Tiny bilingual helper for TAU's UI chrome.
//   LANGS         – the three response-language values
//   t(ko, en, lang) – pick a short label for the current language
//   apiLang(g, o) – resolve which language a tool sends to the backend
//   toolLabel()   – friendly display name for a Work History tool badge
// Long AI *content* is produced bilingually by the backend (Korean then
// English); this file only handles short UI strings.
// ============================================================

export const LANGS = ["한국어", "English", "Bilingual"];

// Short-label translate. Bilingual shows "ko / en" for compact chrome.
export function t(ko, en, lang) {
  if (lang === "한국어") return ko;
  if (lang === "English") return en;
  return `${ko} / ${en}`; // Bilingual
}

// Effective language a tool sends to the backend.
// override === "inherit" (or empty) -> fall back to the global setting.
export function apiLang(globalLang, override) {
  if (!override || override === "inherit") return globalLang;
  return override;
}

// Friendly names for Work History tool badges (future add-ons included).
const TOOL_LABELS = {
  journal: ["분개 도우미", "Journal Entry"],
  term: ["용어 설명", "Term Explainer"],
  file_analyzer: ["파일 분석기", "File Analyzer"],
  reconcile: ["1099 워크시트", "1099 Worksheet"],
  statement_review: ["명세서 검토", "Statement Review"],
  consolidated_workbook: ["통합 워크북", "Consolidated Workbook"],
  data_document_chat: ["데이터·문서 챗", "Data & Document Chat"],
  gl_audit: ["GL 감사 검토", "GL Audit Review Packet"],
};

export function toolLabel(toolName, lang) {
  const pair = TOOL_LABELS[toolName];
  return pair ? t(pair[0], pair[1], lang) : toolName;
}
