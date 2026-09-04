import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { apiFetch, requestJson } from "../../api";
import { artifactsFromProjects } from "./useLineagePage";
import useVersionHistory from "./useVersionHistory";

// File types that own a "duplicate from version" restore endpoint --
// comparison/summary artifacts don't carry their own version-pinned
// content the same way, so they get no restore action here.
const DUPLICATE_ENDPOINT_BY_TYPE = {
  codebook: (ref) => `/api/codebook/${encodeURIComponent(ref)}/duplicate`,
  coding: (ref) => `/api/coding/${encodeURIComponent(ref)}/duplicate`,
  raw_data: (ref) => `/api/data/${encodeURIComponent(ref)}/duplicate`,
  filtered_data: (ref) => `/api/data/${encodeURIComponent(ref)}/duplicate`,
};

/**
 * Backs the standalone Version History page (`/versions?ref=...`) --
 * the one place "Show History" now points to from every workspace/data
 * view/project file row, replacing the inline `VersionHistoryPanel`
 * column that used to live inside the codebook and coding workspaces.
 *
 * Modeled directly on `useLineagePage`: the artifact ref lives in the
 * URL (`?ref=`, falling back to `location.state?.ref` for a redirect
 * that hasn't round-tripped through the address bar yet) so the page is
 * linkable, shareable, and survives a refresh -- exactly what makes
 * "Show History" a plain `navigate()` rather than a modal. The picker
 * reuses the same project-scoped, name-searchable, all-file-types
 * flattening (`artifactsFromProjects`) Lineage already established.
 *
 * `useVersionHistory` (generic across every file type) supplies the
 * actual version list/diff; this hook adds the one thing that ISN'T
 * generic -- which `POST .../duplicate` endpoint "duplicate from this
 * version" calls, since that's a different route per artifact type.
 */
export default function useVersionHistoryPage() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [ref, setRef] = useState(searchParams.get("ref") || location.state?.ref || "");
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");

  const available = useMemo(
    () => artifactsFromProjects(projectsList, selectedProject),
    [projectsList, selectedProject],
  );

  const selectedArtifact = useMemo(
    () => available.find((item) => item.id === ref || item.fileId === String(ref)),
    [available, ref],
  );

  const history = useVersionHistory(ref);

  useEffect(() => {
    let cancelled = false;
    apiFetch("/api/projects/")
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((data) => {
        if (!cancelled && data) setProjectsList(Array.isArray(data.projects) ? data.projects : []);
      })
      .catch((fetchError) => {
        console.error("Error fetching projects:", fetchError);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // A codebook "History" link passes a numeric file id; the picker keys
  // on schema_name. Once the list is in, canonicalize so the row
  // highlights and `?ref=` reads as a stable, shareable schema name.
  useEffect(() => {
    if (!ref || available.length === 0) return;
    const match = available.find((item) => item.id === ref || item.fileId === String(ref));
    if (match && match.id !== ref) {
      setRef(match.id);
      setSearchParams({ ref: match.id });
    }
  }, [available, ref, setSearchParams]);

  const navigateTo = useCallback(
    (nextRef) => {
      setRef(nextRef);
      setSearchParams({ ref: nextRef });
    },
    [setSearchParams],
  );

  const canDuplicate = !!selectedArtifact && !!DUPLICATE_ENDPOINT_BY_TYPE[selectedArtifact.file_type];

  const duplicateFrom = useCallback(
    async (versionNo, displayName) => {
      if (!ref) return { ok: false, error: "No artifact selected." };
      const buildPath = selectedArtifact && DUPLICATE_ENDPOINT_BY_TYPE[selectedArtifact.file_type];
      if (!buildPath) {
        return { ok: false, error: "This artifact type can't be duplicated from history." };
      }
      const result = await requestJson(buildPath(ref), {
        method: "POST",
        body: { display_name: displayName, from_version_no: versionNo || undefined },
      });
      if (!result.ok) return { ok: false, error: result.error };
      return { ok: true };
    },
    [ref, selectedArtifact],
  );

  return {
    ref,
    navigateTo,
    history,
    available,
    projectsList,
    selectedProject,
    setSelectedProject,
    selectedArtifact,
    canDuplicate,
    duplicateFrom: canDuplicate ? duplicateFrom : undefined,
  };
}
