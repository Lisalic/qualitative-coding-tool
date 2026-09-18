import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { apiFetch, requestJson } from "../../api";

export const FILE_TYPE_LABELS = {
  raw_data: "Raw Data",
  filtered_data: "Filtered Data",
  codebook: "Codebook",
  coding: "Coding",
  codebook_comparison: "Codebook Comparison",
  coding_comparison: "Coding Comparison",
  summary: "Summary",
};

export function typeLabel(fileType) {
  return FILE_TYPE_LABELS[fileType] || fileType;
}

function toSelectorItem(file) {
  return {
    id: file.schema_name || String(file.id),
    display_name: file.display_name || file.schema_name || String(file.id),
    description: typeLabel(file.file_type),
    fileId: String(file.id),
    file_type: file.file_type,
  };
}

/** Flatten (and dedupe) project.files into ArtifactPicker items.
 * `selectedProject` narrows to one project; empty means all of them.
 */
export function artifactsFromProjects(projects, selectedProject) {
  const source = selectedProject
    ? projects.filter((project) => String(project.id) === String(selectedProject))
    : projects;
  const seen = new Set();
  const items = [];
  for (const project of source) {
    for (const file of project.files || []) {
      const item = toSelectorItem(file);
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      items.push(item);
    }
  }
  return items;
}

/** Backs the Lineage explorer page: fetch one artifact's typed
 * parents/children (`GET /api/artifacts/{ref}/lineage`), and let the
 * viewer click through a neighbor to re-center the graph on it -- a
 * cheap way to walk the DAG one hop at a time without a full graph
 * layout. The current ref lives in the URL (`?ref=`) so the page is
 * linkable/shareable and survives a refresh.
 *
 * Artifact picking reuses the same project-scoped, name-searchable
 * selector as the other View pages (`ArtifactPicker`), flattened
 * across every file type since lineage is type-agnostic.
 */
export default function useLineagePage() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [ref, setRef] = useState(searchParams.get("ref") || location.state?.ref || "");
  const [lineage, setLineage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");

  // ponytail: picker is project.files only; unattached files still load via ?ref= / Lineage links.
  const available = useMemo(
    () => artifactsFromProjects(projectsList, selectedProject),
    [projectsList, selectedProject],
  );

  const fetchLineage = useCallback(async (targetRef) => {
    if (!targetRef) {
      setLineage(null);
      return;
    }
    setLoading(true);
    setError(null);
    const result = await requestJson(`/api/artifacts/${encodeURIComponent(targetRef)}/lineage`, {
      method: "GET",
    });
    setLoading(false);
    if (!result.ok) {
      setError(result.error || "Failed to load lineage.");
      setLineage(null);
      return;
    }
    setLineage(result.data);
  }, []);

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

  useEffect(() => {
    fetchLineage(ref);
  }, [ref, fetchLineage]);

  // Codebook "Lineage" links pass a numeric file id; the picker keys on
  // schema_name. Once the list is in, canonicalize so the row highlights.
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

  return {
    ref,
    navigateTo,
    lineage,
    loading,
    error,
    available,
    projectsList,
    selectedProject,
    setSelectedProject,
  };
}
