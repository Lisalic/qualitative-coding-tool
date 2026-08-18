const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

export default function DatabaseSourceFields({
  databaseType,
  onDatabaseTypeChange,
  database,
  onDatabaseChange,
  databaseOptions,
  databasePlaceholder = "Select a database",
  selectedProject,
  onProjectChange,
  projectOptions,
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
        <select
          id="database"
          value={database}
          onChange={(e) => onDatabaseChange(e.target.value)}
          className={inputClasses}
          disabled={disabled}
        >
          {!database && (
            <option value="" disabled>
              {databasePlaceholder}
            </option>
          )}
          {databaseOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="project_id" className="text-sm">
          Select Project
        </label>
        <select
          id="project_id"
          value={selectedProject}
          onChange={(e) => onProjectChange(e.target.value)}
          className={inputClasses}
          disabled={disabled}
        >
          {!selectedProject && (
            <option value="" disabled>
              Select a project
            </option>
          )}
          {projectOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}
