// components/LangOverride.js
// A compact per-tool language override. Defaults to "inherit" (use the
// global sidebar setting). Only shown on tools whose backend honors language.
import { LANGS, t } from "./i18n";

export default function LangOverride({ value, onChange, lang }) {
  return (
    <div className="tool-lang">
      <label>{t("이 도구 언어", "This tool", lang)}:</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="inherit">{t("전체 설정 따르기", "Follow global", lang)}</option>
        {LANGS.map((l) => (
          <option key={l} value={l}>{l}</option>
        ))}
      </select>
    </div>
  );
}
