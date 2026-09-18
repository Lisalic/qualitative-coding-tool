import Panel from "../shell/Panel";
import Dropdown from "../primitives/Dropdown";
import { select } from "../../lib/uiClasses";

const selectClasses = `w-full ${select}`;

export default function SummarizeCodingPanel({
  codings,
  selectedCoding,
  onCodingChange,
}) {
  return (
    <Panel title="Select coding" className="flex-1" scroll={false}>
      <div>
        <label className="mb-1 block text-sm">Coding</label>
        <Dropdown
          value={selectedCoding}
          options={codings}
          onChange={onCodingChange}
          placeholder="Select a coding"
          triggerClassName={selectClasses}
          listLabel="Coding"
          searchPlaceholder="Search codings…"
          emptyMessage="No codings match that search."
        />
      </div>
    </Panel>
  );
}
