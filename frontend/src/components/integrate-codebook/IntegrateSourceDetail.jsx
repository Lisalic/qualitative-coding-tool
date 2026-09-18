import Panel from "../shell/Panel";

const FIELDS = [
  ["definition", "Definition"],
  ["inclusion", "Use when"],
  ["exclusion", "Don't use when"],
  ["keywords", "Keywords"],
  ["example", "Example"],
];

/**
 * Reference rail (top): the active source code's full fields, read-only
 * -- mirrors `CodebookReaderPane`'s shape and empty state, one level up
 * (a code rather than a raw data row).
 */
export default function IntegrateSourceDetail({ active, codebookName }) {
  if (!active) {
    return (
      <Panel className="min-h-0 flex-1">
        <p className="italic text-paper/60">Select a code from the list to read it.</p>
      </Panel>
    );
  }

  const { source, family, code } = active;

  return (
    <Panel key={active.key} className="min-h-0 flex-1" bodyClassName="flex flex-col gap-3">
      <div className="min-w-0">
        <div className="text-xs uppercase tracking-wide text-paper/50">
          {codebookName || source.ref}
          {family.family_name ? ` · ${family.family_name}` : ""}
        </div>
        <h3 className="mt-0.5 text-lg font-semibold">{code.name}</h3>
      </div>

      <dl className="flex flex-col gap-2 text-sm">
        {FIELDS.map(([field, label]) =>
          code[field] ? (
            <div key={field}>
              <dt className="text-xs uppercase tracking-wide text-paper/50">{label}</dt>
              <dd className="mt-0.5 whitespace-pre-wrap text-paper/90">{code[field]}</dd>
            </div>
          ) : null,
        )}
      </dl>
    </Panel>
  );
}
