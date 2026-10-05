import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../../api";
import { useRefParam } from "../primitives/useRefParam";

/**
 * Shared read-only "pick one, view its content" hook behind the codebook-
 * comparison and coding-comparison viewers. Parameterized the same way
 * ComparePageContainer/useComparePageData are for the two compare modes,
 * since the two comparison viewers differ only in which file_type/content
 * endpoint they read from.
 */
export default function useViewComparisonPage({
  fileType,
  preselectStateKey,
  contentUrl,
  contentField,
}) {
  const location = useLocation();
  const [available, setAvailable] = useState([]);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [selected, setSelectedRaw] = useState(null);
  // The open comparison lives in the URL as `?ref=` (refresh and Back
  // keep it); a link's `location.state` still wins.
  const urlRef = useRefParam(selected);
  const preselect = location?.state?.[preselectStateKey] || urlRef || null;
  const [listError, setListError] = useState("");
  const [listLoading, setListLoading] = useState(false);
  const [selectedName, setSelectedName] = useState("");
  const [selectedDescription, setSelectedDescription] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // The artifact list refetches for reasons unrelated to the initial
  // "view" navigation (e.g. once the project list finishes loading in),
  // and each refetch used to unconditionally re-apply `preselect` -- which
  // silently snapped the selection back even after the user had since
  // clicked a different item. Track which preselect value has already
  // been applied so it's only ever consumed once per distinct navigation,
  // not once per refetch.
  const appliedPreselectRef = useRef(null);

  const fetchProjects = useCallback(async () => {
    try {
      const resp = await apiFetch("/api/projects/");
      if (!resp.ok) return;
      const data = await resp.json();
      setProjectsList(Array.isArray(data.projects) ? data.projects : []);
    } catch (fetchError) {
      console.error("Error fetching projects:", fetchError);
    }
  }, []);

  const fetchAvailable = useCallback(async () => {
    setListError("");
    setListLoading(true);
    try {
      if (projectsList.length > 0 && selectedProject) {
        const projectObj = projectsList.find(
          (project) => String(project.id) === String(selectedProject),
        );
        const files = (projectObj && projectObj.files) || [];
        const items = files
          .filter((file) => file.file_type === fileType)
          .map((file) => ({
            id: file.schema_name || String(file.id),
            name: file.schema_name || String(file.id),
            display_name: file.display_name || file.schema_name || String(file.id),
            description: file.description || "",
          }));
        setAvailable(items);

        if (!preselect || appliedPreselectRef.current === preselect) return;
        const match = items.find((item) => item.id === preselect);
        if (!match) return;
        appliedPreselectRef.current = preselect;
        setSelectedRaw(preselect);
        setSelectedName(match.display_name || match.name);
        setSelectedDescription(match.description || "");
        return;
      }

      const response = await apiFetch(`/api/my-files/?file_type=${fileType}`);
      if (!response.ok) {
        setListError("Couldn't load your comparisons. Please refresh to try again.");
        return;
      }
      const data = await response.json();
      const items = (data.projects || []).map((project) => ({
        id: project.schema_name || project.id,
        name: project.schema_name || String(project.id),
        display_name: project.display_name || project.schema_name || String(project.id),
        description: project.description || "",
      }));
      setAvailable(items);
      if (!preselect || appliedPreselectRef.current === preselect) return;
      const match = items.find((item) => item.id === preselect);
      if (match) {
        appliedPreselectRef.current = preselect;
        setSelectedRaw(preselect);
        setSelectedName(match.display_name || match.name);
        setSelectedDescription(match.description || "");
      }
    } catch (fetchError) {
      console.error("Error fetching comparisons:", fetchError);
      setListError("Couldn't reach the server to load your comparisons. Check your connection and refresh.");
    } finally {
      setListLoading(false);
    }
  }, [fileType, preselect, projectsList, selectedProject]);

  const setSelected = useCallback(
    (id) => {
      setSelectedRaw(id);
      const match = available.find((item) => item.id === id);
      setSelectedName(match?.display_name || match?.name || id || "");
      setSelectedDescription(match?.description || "");
    },
    [available],
  );

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    fetchAvailable();
  }, [fetchAvailable]);

  useEffect(() => {
    let mounted = true;
    if (!selected) {
      setContent("");
      return () => {
        mounted = false;
      };
    }
    setLoading(true);
    setError(null);
    apiFetch(contentUrl(selected))
      .then((response) => {
        if (!mounted) return null;
        if (!response.ok) {
          throw new Error(
            response.status === 404
              ? "This comparison no longer exists."
              : `Couldn't load this comparison (HTTP ${response.status}).`,
          );
        }
        return response.json();
      })
      .then((data) => {
        if (!mounted || !data) return;
        setContent(data[contentField] || "");
      })
      .catch((fetchError) => {
        if (!mounted) return;
        setError(fetchError.message || "Failed to load comparison");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, contentField]);

  return {
    available,
    projectsList,
    selectedProject,
    setSelectedProject,
    selected,
    setSelected,
    selectedName,
    selectedDescription,
    listError,
    listLoading,
    content,
    loading,
    error,
  };
}
