import { useState } from "react";
import FilterDataPanel from "../components/tool-panels/FilterDataPanel";
import ToolPage from "../components/shell/ToolPage";

export default function Filter() {
  const [filterPrompt, setFilterPrompt] = useState("");

  return (
    <ToolPage>
      <FilterDataPanel
        filterPrompt={filterPrompt}
        onFilterPromptChange={setFilterPrompt}
      />
    </ToolPage>
  );
}
