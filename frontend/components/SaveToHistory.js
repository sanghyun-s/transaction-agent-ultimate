// components/SaveToHistory.js
// Button-driven save used by every tool. `payload` is a function so the
// body is read at click time with fresh values.
import { useState } from "react";
import { API_BASE } from "./api";
import { t } from "./i18n";

export default function SaveToHistory({ payload, lang, disabled }) {
  const [state, setState] = useState("idle"); // idle | saving | saved | error

  const save = async () => {
    setState("saving");
    try {
      const res = await fetch(`${API_BASE}/api/history/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      const data = await res.json();
      setState(data.success ? "saved" : "error");
    } catch {
      setState("error");
    }
  };

  const label = {
    idle: t("작업 기록에 저장", "Save to History", lang),
    saving: t("저장 중...", "Saving...", lang),
    saved: t("✓ 저장됨", "✓ Saved", lang),
    error: t("저장 실패 — 다시 시도", "Save failed — retry", lang),
  }[state];

  return (
    <button
      className="wh-btn"
      style={{ marginTop: "16px" }}
      onClick={state === "error" ? () => setState("idle") : save}
      disabled={disabled || state === "saving" || state === "saved"}
    >
      {label}
    </button>
  );
}
