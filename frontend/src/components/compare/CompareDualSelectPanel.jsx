import React from "react";
import Panel from "../shell/Panel";
import Dropdown from "../primitives/Dropdown";
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
  errors = {},
}) {
  // B never offers what's already chosen as A -- comparing a file with
  // itself isn't a comparison.
  const optionsB = valueA ? options.filter((opt) => opt.value !== valueA) : options;
  return (
    <Panel title={panelTitle} className="flex-1" scroll={false}>
      <div className="mb-3">
        <label htmlFor="compare-a" className="mb-1 block text-sm">
          {labelA}
        </label>
        <Dropdown
          id="compare-a"
          value={valueA}
          options={options}
          onChange={onChangeA}
          placeholder={placeholderOption}
          triggerClassName={selectClasses}
          listLabel={panelTitle}
          emptyMessage="Nothing matches that search."
          noOptionsMessage="Nothing to compare yet."
        />
        {errors.a ? <p className="mt-1 text-xs text-error">{errors.a}</p> : null}
      </div>

      <div className="mb-3">
        <label htmlFor="compare-b" className="mb-1 block text-sm">
          {labelB}
        </label>
        <Dropdown
          id="compare-b"
          value={valueB}
          options={optionsB}
          onChange={onChangeB}
          placeholder={placeholderOption}
          triggerClassName={selectClasses}
          listLabel={panelTitle}
          emptyMessage="Nothing matches that search."
          noOptionsMessage="Nothing else to compare against yet."
        />
        {errors.b ? <p className="mt-1 text-xs text-error">{errors.b}</p> : null}
      </div>
    </Panel>
  );
}
