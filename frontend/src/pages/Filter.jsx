import { useState } from "react";
import PromptManager from "../components/PromptManager";
import FilterDataPanel from "../components/tool-panels/FilterDataPanel";
import "../styles/Home.css";

export default function Filter() {
  const [filterPrompt, setFilterPrompt] = useState("");

  return (
    <div className="home-container">
      <div className="tool-page-layout">
        <div className="left-section">
          <FilterDataPanel
            filterPrompt={filterPrompt}
            onFilterPromptChange={setFilterPrompt}
          />
        </div>
        <div className="prompt-manager-section">
          <PromptManager
            onLoadPrompt={setFilterPrompt}
            currentPrompt={filterPrompt}
            promptType="filter"
          />
        </div>
      </div>
    </div>
  );
}
