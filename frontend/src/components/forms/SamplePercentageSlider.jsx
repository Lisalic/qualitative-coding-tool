export default function SamplePercentageSlider({
  value,
  onChange,
  disabled,
  databaseSelected,
  totalCount,
}) {
  return (
    <div className="form-group">
      <label htmlFor="samplePercentage">Sample Size</label>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <input
            id="samplePercentage"
            type="range"
            min={1}
            max={100}
            step={1}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="slider-input"
            disabled={disabled || !databaseSelected}
          />
          <span
            style={{
              minWidth: "70px",
              textAlign: "right",
              fontWeight: 600,
              color: "#ffffff",
              fontFamily: "system-ui, -apple-system, sans-serif",
            }}
          >
            {databaseSelected ? `${value}%` : ""}
          </span>
        </div>
        <div style={{ marginTop: "6px", fontSize: "0.85em", color: "#999" }}>
          {!databaseSelected
            ? "Select a database to see sampled record counts."
            : (() => {
                const sampleCount = Math.ceil((totalCount * value) / 100);
                return `${sampleCount} of ${totalCount} records will be selected randomly.`;
              })()}
        </div>
      </div>
    </div>
  );
}
