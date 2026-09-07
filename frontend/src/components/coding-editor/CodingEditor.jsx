import { useCallback, useState } from "react";
import ApplyCodebookPanel from "../tool-panels/ApplyCodebookPanel";
import CodingWorkspaceSection from "../coding-table/workspace/CodingWorkspaceSection";
import useViewCodingPage from "../coding-table/workspace/useViewCodingPage";
import PageShell from "../shell/PageShell";
import { btn, btnSm } from "../../lib/uiClasses";

/**
 * Apply Codebook, as one iterative screen.
 *
 * Two steps on one route. **Setup** chooses the source data, the codebook
 * and how to start -- the AI codes every sampled row, or the rows come in
 * uncoded. **Workspace** is the View Coding 3-pane editor, rendered right
 * here on the artifact just created: read a document, tag text by hand,
 * edit the codebook as you learn what it needs, and send any selection of
 * rows back through the AI. Nothing commits until Save Changes, which
 * writes the whole session as one version.
 *
 * The workspace is not a copy of View Coding's -- it IS View Coding's.
 * `CodingWorkspaceSection` and `useViewCodingPage` are shared verbatim;
 * the only difference is that this page pins the artifact it created
 * instead of offering a picker (see `useViewCodingPage`'s `pinnedRef`).
 * Applying a codebook and coding are one activity, and a page that ended
 * at "created" was the seam between them.
 *
 * Notices from an AI run (partial coverage, codings rejected as
 * unverifiable) travel up from the setup panel and are shown above the
 * workspace, since the step that produced them is gone by the time the
 * researcher can act on them.
 */
export default function CodingEditor() {
  const [methodology, setMethodology] = useState("");
  const [artifact, setArtifact] = useState(null);
  const [notices, setNotices] = useState({});

  const page = useViewCodingPage({
    pinned: true,
    pinnedRef: artifact?.schema_name || null,
    pinnedName: artifact?.filename || "",
    pinnedDescription: artifact?.description || "",
  });

  const handleCreated = useCallback((file, runNotices = {}) => {
    if (!file?.schema_name) return;
    setNotices(runNotices || {});
    setArtifact(file);
  }, []);

  const dismissNotice = useCallback((text) => {
    setNotices((prev) =>
      Object.fromEntries(Object.entries(prev).filter(([, value]) => value !== text)),
    );
  }, []);

  const startAnother = useCallback(() => {
    if (
      page.isSessionDirty &&
      !window.confirm("You have unsaved coding changes. Start a new coding and discard them?")
    ) {
      return;
    }
    setArtifact(null);
    setNotices({});
  }, [page.isSessionDirty]);

  if (!artifact) {
    return (
      <PageShell title="Apply Codebook" width="wide">
        <ApplyCodebookPanel
          methodology={methodology}
          onMethodologyChange={setMethodology}
          onCreated={handleCreated}
        />
      </PageShell>
    );
  }

  const noticeText = [notices.partialWarning, notices.codingSummary].filter(Boolean);

  return (
    <>
      {noticeText.length > 0 && (
        <div className="shrink-0 px-4 pt-3">
          {noticeText.map((text) => (
            <div
              key={text}
              className="flex items-start justify-between gap-3 border border-paper bg-surface-raised px-3 py-2 text-sm text-paper"
            >
              <span>{text}</span>
              <button
                type="button"
                className={btnSm}
                onClick={() => dismissNotice(text)}
                aria-label="Dismiss notice"
              >
                Dismiss
              </button>
            </div>
          ))}
        </div>
      )}
      <CodingWorkspaceSection
        page={page}
        leadingActions={
          <button type="button" className={btn} onClick={startAnother}>
            New coding
          </button>
        }
      />
    </>
  );
}
