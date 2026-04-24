import { useState } from "react";
import ApplyCodebookPanel from "../components/tool-panels/ApplyCodebookPanel";
import "../styles/Home.css";

export default function ApplyCodebook() {
  const [methodology, setMethodology] = useState("");

  return (
    <div className="home-container">
      <div className="tool-page-layout">
        <div className="left-section">
          <ApplyCodebookPanel
            methodology={methodology}
            onMethodologyChange={setMethodology}
          />
        </div>
      </div>
    </div>
  );
}
