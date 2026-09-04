import { useState } from "react";
import ApplyCodebookPanel from "../components/tool-panels/ApplyCodebookPanel";
import PageShell from "../components/shell/PageShell";

export default function ApplyCodebook() {
  const [methodology, setMethodology] = useState("");

  return (
    <PageShell title="Apply Codebook" width="wide">
      <ApplyCodebookPanel
        methodology={methodology}
        onMethodologyChange={setMethodology}
      />
    </PageShell>
  );
}
