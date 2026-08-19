import React from "react";

const selectClasses =
  "w-full border border-paper bg-white/5 px-3 py-2 text-paper focus:outline-none focus:ring-2 focus:ring-paper";

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
    <div className="flex flex-1">
      <div className="w-full border-2 border-paper p-5">
        <div className="mb-3">
          <h2 className="text-lg font-semibold">{panelTitle}</h2>
        </div>
        <div className="mb-3">
          <label className="mb-1 block text-sm">{labelA}</label>
          <select
            className={selectClasses}
            value={valueA}
            onChange={(e) => onChangeA(e.target.value)}
          >
            {!valueA && (
              <option value="" disabled>
                {placeholderOption}
              </option>
            )}
            {options.map((it) => (
              <option key={it.value} value={it.value}>
                {it.label}
              </option>
            ))}
          </select>
        </div>

        <div className="mb-3">
          <label className="mb-1 block text-sm">{labelB}</label>
          <select
            className={selectClasses}
            value={valueB}
            onChange={(e) => onChangeB(e.target.value)}
          >
            {!valueB && (
              <option value="" disabled>
                {placeholderOption}
              </option>
            )}
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
