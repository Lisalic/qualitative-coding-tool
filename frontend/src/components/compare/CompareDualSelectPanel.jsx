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
}) {
  return (
    <Panel title={panelTitle} className="flex-1" scroll={false}>
      <div className="mb-3">
        <label className="mb-1 block text-sm">{labelA}</label>
        <Dropdown
          value={valueA}
          options={options}
          onChange={onChangeA}
          placeholder={placeholderOption}
          triggerClassName={selectClasses}
          listLabel={panelTitle}
          emptyMessage="Nothing matches that search."
        />
      </div>

      <div className="mb-3">
        <label className="mb-1 block text-sm">{labelB}</label>
        <Dropdown
          value={valueB}
          options={options}
          onChange={onChangeB}
          placeholder={placeholderOption}
          triggerClassName={selectClasses}
          listLabel={panelTitle}
          emptyMessage="Nothing matches that search."
        />
      </div>
    </Panel>
  );
}
