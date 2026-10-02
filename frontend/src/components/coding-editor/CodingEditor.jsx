import { useState } from "react";
import CodingSetupPanel from "./CodingSetupPanel";
import CodingWorkspaceSection from "../coding-table/workspace/CodingWorkspaceSection";
import useViewCodingPage from "../coding-table/workspace/useViewCodingPage";
import PageShell from "../shell/PageShell";

/**
 * Apply Codebook, as one iterative screen.
 *
 * Two steps on one route. **Setup** chooses the source data and the
 * codebook, then creates the coding artifact uncoded. **Workspace** is
 * the View Coding 3-pane editor, rendered right here on the artifact
 * just created: read a document, tag text by hand, edit the codebook as
 * you learn what it needs, and send any selection of rows through the
 * AI. Nothing commits until Save Changes, which writes the whole session
 * as one version.
 *
 * The workspace is not a copy of View Coding's -- it IS View Coding's.
 * `CodingWorkspaceSection` and `useViewCodingPage` are shared verbatim;
 * the only difference is that this page pins the artifact it created
 * instead of offering a picker (see `useViewCodingPage`'s `pinnedRef`).
 * Applying a codebook and coding are one activity, and a page that ended
 * at "created" was the seam between them.
 */
export default function CodingEditor() {
  const [artifact, setArtifact] = useState(null);

  const page = useViewCodingPage({
    pinned: true,
    pinnedRef: artifact?.schema_name || null,
    pinnedName: artifact?.filename || "",
    pinnedDescription: artifact?.description || "",
  });

  const handleCreated = (file) => {
    if (!file?.schema_name) return;
    setArtifact(file);
  };

  if (!artifact) {
    return (
      <PageShell title="Apply Codebook" width="wide">
        <CodingSetupPanel onCreated={handleCreated} />
      </PageShell>
    );
  }

  return <CodingWorkspaceSection page={page} />;
}
