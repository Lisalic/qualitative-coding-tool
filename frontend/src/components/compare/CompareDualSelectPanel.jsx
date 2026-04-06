import React from "react";

export default function CompareDualSelectPanel({
  panelTitle,
  labelA,
  labelB,
  placeholderOption,
  options,
  valueA,
  valueB,
  onChangeA,
  onChangeB,
}) {
  return (
    <div className="compare-layout-column">
      <div className="compare-panel-card">
        <div className="compare-panel-header">
          <h2 className="compare-panel-title">{panelTitle}</h2>
        </div>
        <div className="compare-form-group">
          <label className="compare-label">{labelA}</label>
          <select
            className="form-input"
            value={valueA}
            onChange={(e) => onChangeA(e.target.value)}
          >
            <option value="">{placeholderOption}</option>
            {options.map((it) => (
              <option key={it.value} value={it.value}>
                {it.label}
              </option>
            ))}
          </select>
        </div>

        <div className="compare-form-group">
          <label className="compare-label">{labelB}</label>
          <select
            className="form-input"
            value={valueB}
            onChange={(e) => onChangeB(e.target.value)}
          >
            <option value="">{placeholderOption}</option>
            {options.map((it) => (
              <option key={it.value} value={it.value}>
                {it.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
