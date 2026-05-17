export default function SliderField({
  id,
  label,
  value,
  onChange,
  min,
  max,
  step,
  disabled,
  valueDisplay,
  valueMinWidth = "60px",
  caption,
}) {
  return (
    <div className="form-group">
      <label htmlFor={id}>{label}</label>
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <input
            id={id}
            type="range"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            className="slider-input"
            disabled={disabled}
          />
          <span
            style={{
              minWidth: valueMinWidth,
              textAlign: "right",
              fontWeight: 600,
              color: "#ffffff",
              fontFamily: "system-ui, -apple-system, sans-serif",
            }}
          >
            {valueDisplay}
          </span>
        </div>
        <div style={{ marginTop: "6px", fontSize: "0.85em", color: "#999" }}>
          {caption}
        </div>
      </div>
    </div>
  );
}
