export default function MinWordsField({
  value,
  onChange,
  disabled,
  rangesLoading,
  caption,
}) {
  return (
    <div className="form-group">
      <label htmlFor="minWords">Minimum Words</label>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <input
            id="minWords"
            type="range"
            min={0}
            max={1000}
            step={10}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="slider-input"
            disabled={disabled}
          />
          <span
            style={{
              minWidth: "60px",
              textAlign: "right",
              fontWeight: 600,
              color: "#ffffff",
              fontFamily: "system-ui, -apple-system, sans-serif",
            }}
          >
            {value}
          </span>
        </div>
        <div style={{ marginTop: "6px", fontSize: "0.85em", color: "#999" }}>
          {rangesLoading ? "Loading word count ranges..." : caption}
        </div>
      </div>
    </div>
  );
}
