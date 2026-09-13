import { useState } from "react";
import ArtifactPicker from "../components/primitives/ArtifactPicker";
import PageShell from "../components/shell/PageShell";
import Panel from "../components/shell/Panel";
import PageEmptyState from "../components/primitives/PageEmptyState";
import PromptPanel from "../components/primitives/PromptPanel";
import useLineagePage, { typeLabel } from "../components/versioning/useLineagePage";
import { hasPromptInfo } from "../lib/promptInfo";
import { badge, btnSm } from "../lib/uiClasses";

function RELATION_LABEL(edge) {
  const roleWord = { source_data: "source data", codebook: "codebook", side_a: "side A", side_b: "side B", merge_input: "merge input", fork_origin: "forked from" }[edge.role] || edge.role;
  return roleWord;
}

const STAGE_LABEL = { generated: "Generated", filter: "Filter assist", codebook: "Codebook assist", coding: "Coding assist", integrate: "Merge assist" };

/** One AI-assist (or one-shot generation) run's model + prompt, behind a
 * per-run toggle -- a source can carry more than one run (e.g. an
 * AI-assisted filter pass, then a separate AI-assisted codebook pass). */
function ProvenanceRun({ run }) {
  const [show, setShow] = useState(false);
  const promptInfo = { systemPrompt: run.system_prompt, instructions: run.user_instructions, promptMeta: run.prompt_meta };
  const canExpand = hasPromptInfo(promptInfo);

  return (
    <div className="flex flex-col gap-1 border border-line/60 px-2 py-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-paper/60">{STAGE_LABEL[run.stage] || run.stage}</span>
        <div className="flex items-center gap-1.5">
          {run.model && <span className={badge}>{run.model}</span>}
          {canExpand && (
            <button type="button" className={btnSm} onClick={(e) => { e.stopPropagation(); setShow((v) => !v); }}>
              {show ? "Hide prompt" : "Show prompt"}
            </button>
          )}
        </div>
      </div>
      {show && <PromptPanel {...promptInfo} />}
    </div>
  );
}

function NeighborCard({ neighbor, onNavigate, direction }) {
  const prompts = neighbor.prompts || [];
  return (
    <div className="flex w-full flex-col gap-1.5 border border-line px-3 py-2 text-sm">
      <button
        type="button"
        onClick={() => onNavigate(neighbor.schema_name)}
        className="flex w-full flex-col items-start gap-1 text-left transition-colors hover:opacity-80"
      >
        <div className="flex w-full items-center justify-between gap-2">
          <span className="truncate font-semibold">{neighbor.filename}</span>
          <span className="shrink-0 border border-line px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-paper/60">
            {typeLabel(neighbor.file_type)}
          </span>
        </div>
        <div className="text-xs text-paper/50">
          {direction === "parent" ? "as " : "role: "}
          {RELATION_LABEL(neighbor)}
          {neighbor.parent_version_no != null ? ` (pinned to v${neighbor.parent_version_no})` : ""}
        </div>
      </button>
      {direction === "parent" && prompts.length > 0 && (
        <div className="flex flex-col gap-1">
          {prompts.map((run, i) => (
            <ProvenanceRun key={`${run.stage}-${i}`} run={run} />
          ))}
        </div>
      )}
    </div>
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
    <PageShell
      title={lineage ? lineage.file.filename : "File Lineage"}
      subtitle={lineage ? `${typeLabel(lineage.file.file_type)} \u00b7 ${lineage.file.schema_name}` : undefined}
      width="wide"
      bodyClassName="flex flex-col gap-3"
      actions={
        <ArtifactPicker
          showProjectFilter={true}
          projects={projectsList}
          selectedProject={selectedProject}
          onProjectChange={setSelectedProject}
          items={available}
          selectedId={ref}
          onSelect={navigateTo}
          emptyMessage="No files available"
          placeholder="Select file…"
        />
      }
    >
      {!ref && !loading && !error ? (
        <PageEmptyState message="Select a file to view its lineage" />
      ) : null}

      {loading && <p className="text-sm text-paper/60">Loading lineage...</p>}
      {error && <p className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{error}</p>}

      {/* Source | this artifact | products, read left to right. The old
          layout stacked all three in a centred max-w-xl column, so a graph
          view occupied a fifth of a wide screen. */}
      {lineage && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <Panel title={`Source (${lineage.parents.length})`} scroll={false} bodyClassName="flex flex-col gap-2">
            {lineage.parents.length === 0 ? (
              <p className="text-sm text-paper/40">No sources -- this is a root file.</p>
            ) : (
              lineage.parents.map((p) => (
                <NeighborCard key={p.id + p.role} neighbor={p} onNavigate={navigateTo} direction="parent" />
              ))
            )}
          </Panel>

          <Panel title="This file" scroll={false}>
            <div className="text-lg font-bold">{lineage.file.filename}</div>
            <div className="text-xs uppercase tracking-wide text-paper/50">
              {typeLabel(lineage.file.file_type)} &middot; {lineage.file.schema_name}
            </div>
          </Panel>

          <Panel title={`Product (${lineage.children.length})`} scroll={false} bodyClassName="flex flex-col gap-2">
            {lineage.children.length === 0 ? (
              <p className="text-sm text-paper/40">Nothing derived from this yet.</p>
            ) : (
              lineage.children.map((c) => (
                <NeighborCard key={c.id + c.role} neighbor={c} onNavigate={navigateTo} direction="child" />
              ))
            )}
          </Panel>
        </div>
      )}
    </PageShell>
  );
}
