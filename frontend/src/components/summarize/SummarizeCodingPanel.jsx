import Panel from "../shell/Panel";
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
        <select
          className={selectClasses}
          value={selectedCoding}
          onChange={(event) => onCodingChange(event.target.value)}
        >
          {!selectedCoding && (
            <option value="" disabled>
              Select a coding
            </option>
          )}
          {codings.map((coding) => (
            <option key={coding.value} value={coding.value}>
              {coding.label}
            </option>
          ))}
        </select>
      </div>
    </Panel>
  );
}
