import AiModelFormGroup from "../models/AiModelFormGroup";

export default function SummarizeFormSection({
  codings,
  selectedCoding,
  onCodingChange,
  model,
  onModelChange,
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 16,
        alignItems: "flex-start",
        marginBottom: 16,
      }}
    >
      <div style={{ flex: 1 }}>
        <label style={{ display: "block", marginBottom: 6 }}>Coding</label>
        <select
          className="form-input"
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

      <div style={{ width: 188, minWidth: 188 }}>
        <AiModelFormGroup
          className=""
          label="Model"
          labelStyle={{ display: "block", marginBottom: 6 }}
          model={model}
          onModelChange={onModelChange}
          selectPlaceholder="dash"
        />
      </div>
    </div>
  );
}
