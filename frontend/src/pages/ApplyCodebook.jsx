import { useState } from "react";
import PromptManager from "../components/PromptManager";
import ApplyCodebookPanel from "../components/tool-panels/ApplyCodebookPanel";
import "../styles/Home.css";

export default function ApplyCodebook() {
  const [methodology, setMethodology] = useState("");

  return (
    <div className="home-container">
      <div className="page-layout">
        <div className="left-section">
          <ApplyCodebookPanel
            methodology={methodology}
            onMethodologyChange={setMethodology}
          />
        </div>
        <div className="manager-section">
          <PromptManager
            onLoadPrompt={setMethodology}
            currentPrompt={methodology}
            promptType="apply"
          />
        </div>
      </div>
    </div>
  );
}
