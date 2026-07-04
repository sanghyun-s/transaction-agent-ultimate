// pages/index.js
// ============================================================
// TAU shell. Holds the global language + active page and composes
// the sidebar with whichever tool component is active. Each tool
// lives in its own file under components/ — so a new add-on is just
// a new component + one nav entry.
// ============================================================
import { useState } from "react";
import Sidebar from "../components/Sidebar";
import JournalEntry from "../components/tools/JournalEntry";
import TermExplainer from "../components/tools/TermExplainer";
import FileAnalyzer from "../components/tools/FileAnalyzer";
import Reconcile from "../components/tools/Reconcile";
import StatementReview from "../components/tools/StatementReview";
import WorkHistory from "../components/WorkHistory";
import { t } from "../components/i18n";

export default function Home() {
  const [activePage, setActivePage] = useState("journal");
  const [language, setLanguage] = useState("한국어");
  // preset lets a sidebar example seed the Journal input (key forces re-apply)
  const [journalPreset, setJournalPreset] = useState({ text: "", key: 0 });

  const onExample = (ex) => {
    setJournalPreset({ text: ex, key: Date.now() });
    setActivePage("journal");
  };

  return (
    <div className="app-layout">
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        language={language}
        onLanguageChange={setLanguage}
        onExample={onExample}
      />

      <main className="main-content">
        <div className="content-wrapper">
          {activePage === "journal" && <JournalEntry language={language} preset={journalPreset} />}
          {activePage === "term" && <TermExplainer language={language} />}
          {activePage === "history" && <WorkHistory language={language} />}
          {activePage === "file" && <FileAnalyzer language={language} />}
          {activePage === "reconcile" && <Reconcile language={language} />}
          {activePage === "statement" && <StatementReview language={language} />}

          <div className="footer">
            ⚠️ {t(
              "이 앱은 학습 목적으로 만들어졌습니다. 실제 회계 처리 시에는 반드시 전문가와 상의하세요.",
              "This app is for learning purposes. Always consult a professional for real accounting work.",
              language
            )}
            <br />
            Frontend: Next.js | Backend: FastAPI | AI: OpenAI GPT-4o-mini + Claude Agent SDK
          </div>
        </div>
      </main>
    </div>
  );
}
