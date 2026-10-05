import Panel from "../shell/Panel";
import Dropdown from "../primitives/Dropdown";
import { select } from "../../lib/uiClasses";

const selectClasses = `w-full ${select}`;

export default function SummarizeCodingPanel({
  codings,
  selectedCoding,
  onCodingChange,
  error,
}) {
  return (
    <Panel title="Select coding" className="flex-1" scroll={false}>
      <div>
        <label htmlFor="summarize-coding" className="mb-1 block text-sm">
          Coding
        </label>
        <Dropdown
          id="summarize-coding"
          value={selectedCoding}
          options={codings}
          onChange={onCodingChange}
          placeholder="Select a coding"
          triggerClassName={selectClasses}
          listLabel="Coding"
          searchPlaceholder="Search codings…"
          emptyMessage="No codings match that search."
          noOptionsMessage="No codings yet. Create one with Apply Codebook first."
        />
        {error ? <p className="mt-1 text-xs text-error">{error}</p> : null}
      </div>
    </Panel>
  );
}
