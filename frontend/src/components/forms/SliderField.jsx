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
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm">
        {label}
      </label>
      <div>
        <div className="flex items-center gap-3">
          <input
            id={id}
            type="range"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) => onChange(Number(e.target.value))}
            disabled={disabled}
            className="h-1.5 flex-1 cursor-pointer appearance-none bg-white/20 accent-paper disabled:cursor-not-allowed disabled:opacity-40"
          />
          <span
            className="text-right font-semibold"
            style={{ minWidth: valueMinWidth }}
          >
            {valueDisplay}
          </span>
        </div>
        <div className="mt-1.5 text-sm text-paper/60">{caption}</div>
      </div>
    </div>
  );
}
