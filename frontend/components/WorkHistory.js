// components/WorkHistory.js
// The shared archive. Lists results from every tool, filterable by tool,
// click-to-reopen, re-download artifacts, delete one, or clear all.
// No semantic recall — this is an archive, by design.
import { useState, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_BASE } from "./api";
import { t, toolLabel } from "./i18n";

export default function WorkHistory({ language }) {
  const [items, setItems] = useState([]);
  const [tools, setTools] = useState([]);
  const [filter, setFilter] = useState("all");
  const [expandedId, setExpandedId] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchHistory = useCallback(async (toolFilter) => {
    setLoading(true);
    try {
      const qs = toolFilter && toolFilter !== "all" ? `?tool=${encodeURIComponent(toolFilter)}` : "";
      const res = await fetch(`${API_BASE}/api/history${qs}`);
      const data = await res.json();
      setItems(data.history || []);
      // Keep the full tool list stable even while filtered.
      if (data.tools && (!toolFilter || toolFilter === "all")) setTools(data.tools);
    } catch {
      setItems([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchHistory("all"); }, [fetchHistory]);

  const onFilter = (value) => {
    setFilter(value);
    setExpandedId(null);
    fetchHistory(value);
  };

  const deleteItem = async (id) => {
    try {
      await fetch(`${API_BASE}/api/history/${id}`, { method: "DELETE" });
      setItems((prev) => prev.filter((x) => x.id !== id));
    } catch {}
  };

  const clearAll = async () => {
    try {
      await fetch(`${API_BASE}/api/history/reset`, { method: "DELETE" });
      setItems([]);
      setTools([]);
      setFilter("all");
    } catch {}
  };

  return (
    <>
      <div className="page-header">
        <h1>📋 {t("작업 기록", "Work History", language)}</h1>
        <p>{t(
          "모든 도구에서 저장한 결과입니다. 클릭하면 다시 열 수 있습니다.",
          "Results you've saved from any tool. Click one to reopen it.",
          language
        )}</p>
      </div>
      <div className="page-divider" />

      {/* Toolbar: filter by tool */}
      <div className="wh-toolbar">
        <label className="wh-filter-label">{t("도구별 보기", "View by tool", language)}:</label>
        <select className="wh-filter" value={filter} onChange={(e) => onFilter(e.target.value)}>
          <option value="all">{t("전체", "All tools", language)}</option>
          {tools.map((tn) => (
            <option key={tn} value={tn}>{toolLabel(tn, language)}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /><span>{t("불러오는 중...", "Loading...", language)}</span></div>
      ) : items.length === 0 ? (
        <div className="info-msg">{t(
          "아직 저장된 작업이 없습니다. 각 도구에서 “작업 기록에 저장”을 눌러보세요.",
          "Nothing saved yet. Use “Save to History” on any tool.",
          language
        )}</div>
      ) : (
        <>
          {items.map((item) => (
            <div key={item.id} className="history-item">
              <div className="history-header" onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}>
                <span>
                  <span className="wh-badge">{toolLabel(item.tool_name, language)}</span>
                  📄 {item.title || t("(제목 없음)", "(untitled)", language)}
                </span>
                <span className="timestamp">{item.created_at}</span>
              </div>
              {expandedId === item.id && (
                <div className="history-body">
                  {item.output_format === "html" ? (
                    <div dangerouslySetInnerHTML={{ __html: item.output_content }} />
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {item.output_content || item.output_preview || ""}
                    </ReactMarkdown>
                  )}
                  <div className="wh-actions">
                    {item.artifact_path && (
                      <a className="wh-btn" href={`${API_BASE}/api/history/${item.id}/download`}>
                        {t("첨부 다운로드", "Download attachment", language)}
                      </a>
                    )}
                    <button className="wh-btn wh-btn-danger" onClick={() => deleteItem(item.id)}>
                      {t("삭제", "Delete", language)}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}

          <div className="page-divider" />
          <button className="clear-btn" onClick={clearAll}>
            🗑️ {t("전체 기록 삭제", "Clear all history", language)}
          </button>
        </>
      )}
    </>
  );
}
