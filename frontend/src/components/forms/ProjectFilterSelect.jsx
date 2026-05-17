export default function ProjectFilterSelect({
  projects = [],
  value = "",
  onChange,
  label = "Project:",
  allLabel = "All Projects",
  className = "",
  selectClassName = "",
  style,
}) {
  return (
    <div className={className} style={style}>
      <label style={{ color: "#fff", marginRight: 8 }}>{label}</label>
      <select
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className={selectClassName}
        style={!selectClassName ? { padding: "6px 8px", borderRadius: 6 } : null}
      >
        <option value="">{allLabel}</option>
        {(projects || []).map((project) => (
          <option key={project.id} value={String(project.id)}>
            {project.projectname || project.display_name || project.schema_name || project.id}
          </option>
        ))}
      </select>
    </div>
  );
}
