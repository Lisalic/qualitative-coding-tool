import EditorListPane from "../editor-shell/EditorListPane";
import { btnSm } from "../../lib/uiClasses";

function codeKeyFor(ref, familyUid, codeUid) {
  return `${ref}::${familyUid}::${codeUid}`;
}

/**
 * Left pane: every code in every source codebook being integrated,
 * grouped by codebook then family -- read-only, since nothing here is
 * decided per code the way a filter/apply editor's row list is. "Add"
 * copies a source code straight into the draft, the rescue path for
 * anything the assistant drops or merges into something the researcher
 * disagrees with.
 *
 * Deliberately has no per-code "already merged" marker. An earlier
 * version set one on accept/copy and never cleared it, which drifted
 * from the truth the moment the researcher renamed, re-merged, or
 * deleted the resulting draft code -- exactly the editing this tool
 * exists to support. `editor.copyCode` still guards against adding an
 * exact duplicate (checked fresh each click, see
 * `lib/codebookEditorState.js::copySourceCode`), so nothing here needs
 * to track coverage to avoid clutter. The footer's live draft count is
 * the actual progress signal.
 */
export default function IntegrateSourcePane({
  sources,
  codebookNames,
  loading,
  activeKey,
  onSelectCode,
  draftCount,
  onCopyCode,
  disabled,
}) {
  const totalCodes = sources.reduce((sum, s) => sum + s.tree.reduce((n, f) => n + f.codes.length, 0), 0);

  return (
    <EditorListPane
      loading={loading}
      loadingMessage="Loading source codebooks..."
      isEmpty={sources.length === 0}
      emptyMessage="No source codebooks loaded."
      header={<span className="text-xs text-paper/70">{sources.length} codebooks · {totalCodes} codes</span>}
      footer={
        <span className="text-xs text-paper/60">
          {draftCount} code{draftCount === 1 ? "" : "s"} in your draft so far
        </span>
      }
    >
      {sources.map((source) => (
        <div key={source.ref} className="border-b border-line-soft">
          <div className="bg-white/5 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-paper/70">
            {codebookNames[source.ref] || source.ref}
          </div>
          {source.tree.map((family) => (
            <div key={family.family_uid}>
              {family.family_name ? (
                <div className="px-3 pt-1.5 text-[11px] uppercase tracking-wide text-paper/40">
                  {family.family_name}
                </div>
              ) : null}
              <ul>
                {family.codes.map((code) => {
                  const key = codeKeyFor(source.ref, family.family_uid, code.code_uid);
                  const isActive = key === activeKey;
                  return (
                    <li
                      key={key}
                      className={`flex items-center justify-between gap-2 px-3 py-1.5 transition-colors ${
                        isActive ? "bg-paper text-ink" : "hover:bg-white/5"
                      }`}
                    >
                      <button
                        type="button"
                        className="min-w-0 flex-1 truncate text-left text-sm"
                        onClick={() => onSelectCode({ key, source, family, code })}
                      >
                        {code.name}
                      </button>
                      <button
                        type="button"
                        className={`shrink-0 ${btnSm}`}
                        disabled={disabled}
                        aria-label={`Add ${code.name} to the draft`}
                        onClick={() =>
                          onCopyCode({
                            family_name: family.family_name,
                            name: code.name,
                            definition: code.definition,
                            inclusion: code.inclusion,
                            exclusion: code.exclusion,
                            keywords: code.keywords,
                            example: code.example,
                          })
                        }
                      >
                        Add
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      ))}
    </EditorListPane>
  );
}
