import Dropdown from "../primitives/Dropdown";
import { pillRadioInput, pillRadioLabel, select } from "../../lib/uiClasses";

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
      <fieldset className="min-w-0">
        <legend className="mb-1.5 text-sm">Database type</legend>
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
                className={pillRadioInput}
              />
              <label htmlFor={`${radioName}-${opt.value}`} className={pillRadioLabel}>
                {opt.label}
              </label>
            </div>
          ))}
        </div>
      </fieldset>

      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${radioName}-database`} className="text-sm">
          Database
        </label>
        <Dropdown
          id={`${radioName}-database`}
          value={database}
          options={databaseOptions}
          onChange={onDatabaseChange}
          placeholder={databasePlaceholder}
          disabled={disabled}
          triggerClassName={`w-full ${select}`}
          listLabel="Database"
          searchPlaceholder="Search databases…"
          emptyMessage="No databases match that search."
          noOptionsMessage="No databases yet. Import data first."
        />
      </div>
    </>
  );
}
