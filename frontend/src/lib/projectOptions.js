/**
 * One way to label and list projects in a dropdown.
 *
 * Four call sites each had their own coalescing chain -- `projectname` alone
 * in the compare/summarize panels, `projectname || display_name || name || id`
 * in the editors' output fields, and `projectname || display_name ||
 * schema_name || id` in the file picker -- so the same project could render
 * under different names depending on the page.
 */
export function projectLabel(project) {
  return (
    project.projectname ||
    project.display_name ||
    project.name ||
    project.schema_name ||
    String(project.id)
  );
}

/** `{value,label}` options for a `Dropdown`. Ids are stringified, since that
 * is what every project-owning form posts back. */
export function toProjectOptions(projects) {
  return (projects || []).map((project) => ({
    value: String(project.id),
    label: projectLabel(project),
  }));
}
