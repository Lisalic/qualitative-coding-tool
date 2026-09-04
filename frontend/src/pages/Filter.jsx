import { useState } from "react";
import FilterDataPanel from "../components/tool-panels/FilterDataPanel";
import PageShell from "../components/shell/PageShell";

export default function Filter() {
  const [filterPrompt, setFilterPrompt] = useState("");

  return (
    <PageShell title="Apply Filter" width="wide">
      <FilterDataPanel
        filterPrompt={filterPrompt}
        onFilterPromptChange={setFilterPrompt}
      />
    </PageShell>
  );
}
