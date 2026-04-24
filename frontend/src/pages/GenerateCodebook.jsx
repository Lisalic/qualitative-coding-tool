import { useState } from "react";
import GenerateCodebookPanel from "../components/tool-panels/GenerateCodebookPanel";
import "../styles/Home.css";

export default function GenerateCodebook() {
  const [prompt, setPrompt] = useState("");

  return (
    <div className="home-container">
      <div className="tool-page-layout">
        <div className="left-section">
          <GenerateCodebookPanel prompt={prompt} onPromptChange={setPrompt} />
        </div>
      </div>
    </div>
  );
}
