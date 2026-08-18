const selectClasses =
  "w-full border border-paper bg-white/5 px-3 py-2 text-paper focus:outline-none focus:ring-2 focus:ring-paper";

export default function SummarizeCodingPanel({ codings, selectedCoding, onCodingChange }) {
  return (
    <div className="flex flex-1">
      <div className="w-full border-2 border-paper p-5">
        <div className="mb-3">
          <h2 className="text-lg font-semibold">Select coding</h2>
        </div>
        <div>
          <label className="mb-1 block text-sm">Coding</label>
          <select
            className={selectClasses}
            value={selectedCoding}
            onChange={(event) => onCodingChange(event.target.value)}
          >
            <option value="">-- select --</option>
            {codings.map((coding) => (
              <option key={coding.value} value={coding.value}>
                {coding.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
