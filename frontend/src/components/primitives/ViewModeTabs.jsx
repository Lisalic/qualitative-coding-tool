export default function ViewModeTabs({
  modes,
  activeMode,
  onChange,
  disabled,
  containerStyle,
  containerClassName,
}) {
  if (disabled) return null;

  return (
    <div className={containerClassName} style={containerStyle}>
      {modes.map(
        ({
          value,
          label,
          className,
          activeClassName,
          inactiveClassName,
          style,
          disableWhenActive,
        }) => {
          const isActive = activeMode === value;
          const buttonClassName = isActive
            ? activeClassName || className || "view-button"
            : inactiveClassName || className || "view-button";

          return (
            <button
              key={value}
              className={buttonClassName}
              onClick={() => onChange(value)}
              aria-pressed={isActive}
              disabled={disableWhenActive && isActive}
              style={style}
            >
              {label}
            </button>
          );
        },
      )}
    </div>
  );
}
