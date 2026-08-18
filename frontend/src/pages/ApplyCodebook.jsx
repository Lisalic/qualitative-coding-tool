import { useState } from "react";
import ApplyCodebookPanel from "../components/tool-panels/ApplyCodebookPanel";
import ToolPage from "../components/shell/ToolPage";

export default function ApplyCodebook() {
  const [methodology, setMethodology] = useState("");

  return (
    <ToolPage>
      <ApplyCodebookPanel
        methodology={methodology}
        onMethodologyChange={setMethodology}
      />
    </ToolPage>
  );
}
