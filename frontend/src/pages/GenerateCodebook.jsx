import { useState } from "react";
import GenerateCodebookPanel from "../components/tool-panels/GenerateCodebookPanel";
import PageShell from "../components/shell/PageShell";

export default function GenerateCodebook() {
  const [prompt, setPrompt] = useState("");

  return (
    <PageShell title="Generate Codebook" width="wide">
      <GenerateCodebookPanel prompt={prompt} onPromptChange={setPrompt} />
    </PageShell>
  );
}
