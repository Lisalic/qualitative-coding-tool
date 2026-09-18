import Dropdown from "../primitives/Dropdown";
import { select } from "../../lib/uiClasses";

/**
 * Database type + database picker, shared by whichever editor's setup
 * step needs to choose a source. Project association is a separate
 * concern -- see `EditorOutputFields` -- so it isn't duplicated here.
 */
export default function DatabaseSourceFields({
  databaseType,
  onDatabaseTypeChange,
  database,
  onDatabaseChange,
  databaseOptions,
  databasePlaceholder = "Select a database",
  disabled,
  radioName = "databaseType",
}) {
  return (
    <>
      <div className="flex flex-col gap-1.5">
        <label className="text-sm">Database Type</label>
        <div className="flex w-full gap-2">
          {[
            { value: "unfiltered", label: "Unfiltered Databases" },
            { value: "filtered", label: "Filtered Databases" },
          ].map((opt) => (
            <div key={opt.value} className="flex-1">
              <input
                type="radio"
                id={`${radioName}-${opt.value}`}
                name={radioName}
                value={opt.value}
                checked={databaseType === opt.value}
                onChange={() => onDatabaseTypeChange(opt.value)}
                disabled={disabled}
                className="peer hidden"
              />
              <label
                htmlFor={`${radioName}-${opt.value}`}
                className="block cursor-pointer border border-paper px-3 py-2 text-center text-sm transition-colors hover:bg-paper hover:text-ink peer-checked:bg-paper peer-checked:text-ink"
              >
                {opt.label}
              </label>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="database" className="text-sm">
          Select Database
        </label>
        <Dropdown
          id="database"
          value={database}
          options={databaseOptions}
          onChange={onDatabaseChange}
          placeholder={databasePlaceholder}
          disabled={disabled}
          triggerClassName={`w-full ${select}`}
          listLabel="Database"
          searchPlaceholder="Search databases…"
          emptyMessage="No databases match that search."
        />
      </div>
    </>
  );
}
