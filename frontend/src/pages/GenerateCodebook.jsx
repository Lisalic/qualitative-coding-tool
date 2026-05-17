import { useState } from "react";
import GenerateCodebookPanel from "../components/tool-panels/GenerateCodebookPanel";
import ToolPage from "../components/shell/ToolPage";
import "../styles/Home.css";

export default function GenerateCodebook() {
  const [prompt, setPrompt] = useState("");

  return (
    <ToolPage>
      <GenerateCodebookPanel prompt={prompt} onPromptChange={setPrompt} />
    </ToolPage>
  );
}
