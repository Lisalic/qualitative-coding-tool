import ArtifactSelector from "../components/primitives/ArtifactSelector";
import ViewPageShell from "../components/shell/ViewPageShell";
import useLineagePage, { typeLabel } from "../components/versioning/useLineagePage";

function RELATION_LABEL(edge) {
  const roleWord = { source_data: "source data", codebook: "codebook", side_a: "side A", side_b: "side B", merge_input: "merge input", fork_origin: "forked from" }[edge.role] || edge.role;
  return roleWord;
}

function NeighborCard({ neighbor, onNavigate, direction }) {
  return (
    <button
      type="button"
      onClick={() => onNavigate(neighbor.schema_name)}
      className="flex w-full flex-col items-start gap-1 border border-paper/30 px-3 py-2 text-left text-sm transition-colors hover:border-paper hover:bg-white/5"
    >
      <div className="flex w-full items-center justify-between gap-2">
        <span className="truncate font-semibold">{neighbor.filename}</span>
        <span className="shrink-0 border border-paper/30 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-paper/60">
          {typeLabel(neighbor.file_type)}
        </span>
      </div>
      <div className="text-xs text-paper/50">
        {direction === "parent" ? "as " : "role: "}
        {RELATION_LABEL(neighbor)}
        {neighbor.parent_version_no != null ? ` (pinned to v${neighbor.parent_version_no})` : ""}
      </div>
    </button>
  );
}

/**
 * A one-hop lineage explorer: the current artifact in the middle, its
 * typed parents above and typed children below (see
 * `backend/app/api/version_routes.py::lineage`, GAP C6). Clicking a
 * neighbor re-centers the graph on it, so the whole DAG is reachable by
 * walking edge by edge without a heavyweight graph-layout library.
 */
export default function Lineage() {
  const {
    ref,
    navigateTo,
    lineage,
    loading,
    error,
    available,
    projectsList,
    selectedProject,
    setSelectedProject,
  } = useLineagePage();

  return (
    <ViewPageShell title="Artifact Lineage">
      <ArtifactSelector
        showProjectFilter={true}
        projects={projectsList}
        selectedProject={selectedProject}
        onProjectChange={setSelectedProject}
        items={available}
        selectedId={ref}
        onSelect={navigateTo}
        emptyMessage="No artifacts available"
      />

      {loading && <p className="text-sm text-paper/60">Loading lineage...</p>}
      {error && <p className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{error}</p>}

      {lineage && (
        <div className="flex flex-col items-center gap-4">
          <div className="flex w-full max-w-xl flex-col gap-2">
            <p className="text-center text-xs font-semibold uppercase tracking-wide text-paper/50">
              Parents ({lineage.parents.length})
            </p>
            {lineage.parents.length === 0 ? (
              <p className="text-center text-sm text-paper/40">No parents -- this is a root artifact.</p>
            ) : (
              lineage.parents.map((p) => (
                <NeighborCard key={p.id + p.role} neighbor={p} onNavigate={navigateTo} direction="parent" />
              ))
            )}
          </div>

          <div className="w-full max-w-xl border-2 border-paper px-3 py-2.5 text-center">
            <div className="text-lg font-bold">{lineage.file.filename}</div>
            <div className="text-xs uppercase tracking-wide text-paper/50">
              {typeLabel(lineage.file.file_type)} &middot; {lineage.file.schema_name}
            </div>
          </div>

          <div className="flex w-full max-w-xl flex-col gap-2">
            <p className="text-center text-xs font-semibold uppercase tracking-wide text-paper/50">
              Children ({lineage.children.length})
            </p>
            {lineage.children.length === 0 ? (
              <p className="text-center text-sm text-paper/40">Nothing derived from this yet.</p>
            ) : (
              lineage.children.map((c) => (
                <NeighborCard key={c.id + c.role} neighbor={c} onNavigate={navigateTo} direction="child" />
              ))
            )}
          </div>
        </div>
      )}
    </ViewPageShell>
  );
}
