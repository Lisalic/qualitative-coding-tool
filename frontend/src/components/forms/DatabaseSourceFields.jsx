import "../../styles/Home.css";

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
      <div className="form-group">
        <label>Database Type</label>
        <div className="radio-group">
          {[
            { value: "unfiltered", label: "Unfiltered Databases" },
            { value: "filtered", label: "Filtered Databases" },
          ].map((opt) => (
            <div key={opt.value}>
              <input
                type="radio"
                id={`${radioName}-${opt.value}`}
                name={radioName}
                value={opt.value}
                checked={databaseType === opt.value}
                onChange={() => onDatabaseTypeChange(opt.value)}
                disabled={disabled}
                style={{ display: "none" }}
              />
              <label
                htmlFor={`${radioName}-${opt.value}`}
                className="radio-label"
              >
                {opt.label}
              </label>
            </div>
          ))}
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="database">Select Database</label>
        <select
          id="database"
          value={database}
          onChange={(e) => onDatabaseChange(e.target.value)}
          className="form-input"
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

      <div className="form-group">
        <label htmlFor="project_id">Select Project</label>
        <select
          id="project_id"
          value={selectedProject}
          onChange={(e) => onProjectChange(e.target.value)}
          className="form-input"
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
