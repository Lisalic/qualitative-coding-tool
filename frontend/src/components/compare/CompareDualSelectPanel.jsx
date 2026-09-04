import React from "react";
import Panel from "../shell/Panel";
import { select } from "../../lib/uiClasses";

const selectClasses = `w-full ${select}`;

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
    <Panel title={panelTitle} className="flex-1" scroll={false}>
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
    </Panel>
  );
}
