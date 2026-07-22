// components/tools/DataDocumentChat.js
// CASSIA add-on (minimal). Chat-first: the thread + router are always here;
// nothing loaded → general accounting Q&A. Upload is a SIDE action that loads a
// CSV/Excel (→ SQL) or PDF (→ RAG) into a single sticky session (survives
// refresh via sessionStorage, dies on tab close). "New chat" resets the session.
import { useState, useEffect, useRef } from "react";
import { API_BASE } from "../api";
import { t } from "../i18n";
import SaveToHistory from "../SaveToHistory";

const SS_KEY = "tau_chat_session";
const genId = () => "s-" + Math.random().toString(36).slice(2) + Date.now().toString(36);

const ROUTE_BADGE = {
  sql: { label: ["SQL", "SQL"], bg: "#E1F5EE", fg: "#0F6E56" },
  rag: { label: ["문서", "Doc"], bg: "#EEEDFE", fg: "#3C3489" },
  general: { label: ["일반", "General"], bg: "#F1EFE8", fg: "#5F5E5A" },
};

export default function DataDocumentChat({ language }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);      // {role, content, route?}
  const [loadedFiles, setLoadedFiles] = useState([]); // [{name, kind}]
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef(null);
  const threadRef = useRef(null);

  // Restore (or create) the sticky session, and re-sync what's loaded on the backend.
  useEffect(() => {
    let id = typeof window !== "undefined" && window.sessionStorage.getItem(SS_KEY);
    if (!id) { id = genId(); window.sessionStorage.setItem(SS_KEY, id); }
    setSessionId(id);
    fetch(`${API_BASE}/api/chat/state?session_id=${encodeURIComponent(id)}`)
      .then((r) => r.json())
      .then((d) => d && d.loaded_files && setLoadedFiles(d.loaded_files))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages, sending]);

  const onUpload = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file || !sessionId) return;
    setUploading(true); setError("");
    const fd = new FormData();
    fd.append("session_id", sessionId);
    fd.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/api/chat/upload`, { method: "POST", body: fd });
      const data = await res.json();
      if (!data.success) {
        setError(data.error || t("업로드 실패", "Upload failed", language));
      } else {
        setLoadedFiles(data.loaded_files || []);
        const kindLabel = data.kind === "table"
          ? t("표 데이터", "table", language) : t("문서", "document", language);
        setMessages((m) => [...m, {
          role: "system",
          content: t(`${file.name} 불러옴 (${kindLabel}) — 이제 질문하세요.`,
                     `Loaded ${file.name} (${kindLabel}) — ask away.`, language),
        }]);
      }
    } catch {
      setError(t("백엔드에 연결할 수 없습니다.", "Cannot connect to backend.", language));
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const send = async () => {
    const q = input.trim();
    if (!q || !sessionId || sending) return;
    setInput(""); setError("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setSending(true);
    const fd = new FormData();
    fd.append("session_id", sessionId);
    fd.append("question", q);
    fd.append("language", language);
    try {
      const res = await fetch(`${API_BASE}/api/chat/ask`, { method: "POST", body: fd });
      const data = await res.json();
      if (!data.success || data.answer == null) {
        setMessages((m) => [...m, { role: "assistant",
          content: "⚠️ " + (data.error || t("답변 실패", "No answer", language)) }]);
      } else {
        setMessages((m) => [...m, { role: "assistant", content: data.answer, route: data.route }]);
      }
    } catch {
      setMessages((m) => [...m, { role: "assistant",
        content: "⚠️ " + t("백엔드에 연결할 수 없습니다.", "Cannot connect to backend.", language) }]);
    }
    setSending(false);
  };

  const newChat = async () => {
    if (sessionId) {
      try { await fetch(`${API_BASE}/api/chat/reset`, {
        method: "POST",
        body: (() => { const f = new FormData(); f.append("session_id", sessionId); return f; })(),
      }); } catch {}
    }
    const id = genId();
    window.sessionStorage.setItem(SS_KEY, id);
    setSessionId(id);
    setMessages([]); setLoadedFiles([]); setInput(""); setError("");
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const historyMarkdown = () => {
    const L = [`# ${t("데이터·문서 채팅", "Data & Document Chat", language)}`];
    if (loadedFiles.length) L.push(`_${t("불러온 파일", "Loaded", language)}: ${loadedFiles.map((f) => f.name).join(", ")}_`, "");
    messages.filter((m) => m.role !== "system").forEach((m) => {
      const who = m.role === "user" ? t("질문", "You", language) : t("답변", "Assistant", language);
      L.push(`**${who}${m.route ? ` (${m.route})` : ""}:** ${m.content}`, "");
    });
    return L.join("\n");
  };

  const answered = messages.some((m) => m.role === "assistant");

  return (
    <>
      <div className="page-header">
        <h1>💬 {t("데이터·문서 채팅", "Data & Document Chat", language)}</h1>
        <p>{t(
          "회계 질문을 자유롭게 하세요. CSV·엑셀을 올리면 표를 질의(SQL)하고, PDF를 올리면 문서에서 근거를 찾아 답합니다.",
          "Ask accounting questions freely. Add a CSV/Excel to query the table (SQL), or a PDF to answer from the document (RAG).",
          language
        )}</p>
      </div>
      <div className="page-divider" />

      {/* Data bar — upload is a side action; it never blocks the chat */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", marginBottom: "12px" }}>
        <button type="button" className="submit-btn" style={{ width: "auto", padding: "8px 14px" }}
          onClick={() => fileRef.current && fileRef.current.click()} disabled={uploading || !sessionId}>
          {uploading ? t("불러오는 중...", "Loading...", language) : t("＋ 데이터 추가", "＋ Add data", language)}
        </button>
        <input ref={fileRef} type="file" accept=".csv,.tsv,.xlsx,.xls,.pdf"
          style={{ display: "none" }} onChange={onUpload} />

        {loadedFiles.length > 0 ? (
          <span style={{ fontSize: "0.85rem", color: "#5F5E5A" }}>
            {t("불러옴", "Loaded", language)}: {loadedFiles.map((f, i) => (
              <span key={i} style={{ marginLeft: i ? "6px" : "4px", padding: "2px 8px", borderRadius: "10px",
                background: f.kind === "table" ? "#E1F5EE" : "#EEEDFE",
                color: f.kind === "table" ? "#0F6E56" : "#3C3489" }}>{f.name}</span>
            ))}
          </span>
        ) : (
          <span style={{ fontSize: "0.85rem", color: "#888780" }}>
            {t("CSV·엑셀·PDF (선택) — 없어도 일반 질문 가능", "CSV/Excel/PDF (optional) — general questions work with nothing loaded", language)}
          </span>
        )}

        <button type="button" onClick={newChat}
          style={{ marginLeft: "auto", background: "none", border: "1px solid #D3D1C7", borderRadius: "8px",
                   padding: "7px 12px", fontSize: "0.85rem", color: "#5F5E5A", cursor: "pointer" }}>
          {t("새 대화", "New chat", language)}
        </button>
      </div>

      {/* Chat thread */}
      <div ref={threadRef} style={{ border: "1px solid #E6E4DC", borderRadius: "12px", padding: "16px",
        minHeight: "260px", maxHeight: "460px", overflowY: "auto", background: "#FCFBF8" }}>
        {messages.length === 0 && (
          <p style={{ color: "#888780", fontSize: "0.9rem", margin: 0 }}>
            {t("예: “1099-NEC란 무엇인가요?” 또는 데이터를 올린 뒤 “벤더가 몇 곳인가요?”",
               "e.g. \u201CWhat is a 1099-NEC?\u201D — or add data, then \u201Chow many vendors are there?\u201D", language)}
          </p>
        )}
        {messages.map((m, i) => {
          if (m.role === "system") return (
            <div key={i} style={{ textAlign: "center", fontSize: "0.8rem", color: "#888780", margin: "8px 0" }}>{m.content}</div>
          );
          const isUser = m.role === "user";
          const badge = m.route && ROUTE_BADGE[m.route];
          return (
            <div key={i} style={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start", margin: "8px 0" }}>
              <div style={{ maxWidth: "82%", padding: "10px 14px", borderRadius: "12px",
                background: isUser ? "#1D3B6E" : "#FFFFFF", color: isUser ? "#FFFFFF" : "#2C2C2A",
                border: isUser ? "none" : "1px solid #E6E4DC", whiteSpace: "pre-wrap", lineHeight: 1.55 }}>
                {badge && (
                  <span style={{ display: "inline-block", fontSize: "0.7rem", fontWeight: 600, marginBottom: "4px",
                    padding: "1px 7px", borderRadius: "9px", background: badge.bg, color: badge.fg }}>
                    {t(badge.label[0], badge.label[1], language)}
                  </span>
                )}
                <div>{m.content}</div>
              </div>
            </div>
          );
        })}
        {sending && (
          <div style={{ display: "flex", justifyContent: "flex-start", margin: "8px 0" }}>
            <div style={{ padding: "10px 14px", borderRadius: "12px", background: "#FFFFFF", border: "1px solid #E6E4DC", color: "#888780" }}>
              {t("생각 중...", "Thinking...", language)}
            </div>
          </div>
        )}
      </div>

      {error && <div className="error-msg" style={{ marginTop: "10px" }}>⚠️ {error}</div>}

      {/* Composer */}
      <div style={{ display: "flex", gap: "8px", marginTop: "12px", alignItems: "flex-end" }}>
        <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKeyDown}
          rows={2} placeholder={t("질문을 입력하세요...", "Type your question...", language)}
          style={{ flex: 1, resize: "vertical", padding: "10px 12px", borderRadius: "10px",
                   border: "1px solid #D3D1C7", fontFamily: "inherit", fontSize: "0.95rem" }} />
        <button className="submit-btn" style={{ width: "auto", padding: "10px 20px" }}
          onClick={send} disabled={sending || !input.trim() || !sessionId}>
          {t("보내기", "Send", language)}
        </button>
      </div>

      {answered && (
        <div style={{ marginTop: "14px" }}>
          <SaveToHistory
            lang={language}
            payload={() => ({
              tool_name: "data_document_chat",
              title: t("데이터·문서 채팅", "Data & Document Chat", language)
                + (loadedFiles.length ? ` — ${loadedFiles.map((f) => f.name).join(", ")}` : ""),
              language,
              input_summary: `${messages.filter((m) => m.role === "user").length} Q · ${loadedFiles.length} file(s) loaded`,
              output_content: historyMarkdown(),
              output_format: "markdown",
            })}
          />
        </div>
      )}
    </>
  );
}
