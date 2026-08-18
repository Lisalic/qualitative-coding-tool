export default function ProjectFilterSelect({
  projects = [],
  value = "",
  onChange,
  label = "Project:",
  allLabel = "All Projects",
  className = "mb-4 flex items-center gap-2",
  selectClassName = "border border-paper bg-white/5 px-3 py-2 text-paper focus:outline-none focus:ring-2 focus:ring-paper",
  style,
}) {
  return (
    <div className={className} style={style}>
      <label className="text-sm">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        className={selectClassName}
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
