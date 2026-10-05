import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../../api";
import { useRefParam } from "../primitives/useRefParam";

export default function useViewSummaryPage() {
  const location = useLocation();
  const [available, setAvailable] = useState([]);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [selected, setSelected] = useState(null);
  // The open summary lives in the URL as `?ref=` (refresh and Back keep
  // it); a link's `location.state.selectedSummary` still wins.
  const urlRef = useRefParam(selected);
  const preselect = location?.state?.selectedSummary || urlRef || null;
  const [listError, setListError] = useState("");
  const [listLoading, setListLoading] = useState(false);
  const [selectedName, setSelectedName] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // The summary list refetches for reasons unrelated to the initial "view"
  // navigation (e.g. once the project list finishes loading in), and each
  // refetch used to unconditionally re-apply the location.state
  // preselection -- which silently snapped the selection back even after
  // the user had since clicked a different summary. Track which preselect
  // value has already been applied so it's only ever consumed once per
  // distinct navigation, not once per refetch.
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

  const fetchAvailableSummaries = useCallback(async () => {
    setListError("");
    setListLoading(true);
    try {
      if (projectsList.length > 0 && selectedProject) {
        const projectObj = projectsList.find(
          (project) => String(project.id) === String(selectedProject),
        );
        const files = (projectObj && projectObj.files) || [];
        const items = files
          .filter((file) => file.file_type === "summary")
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
        setSelected(preselect);
        setSelectedName(match.display_name || match.name);
        return;
      }

      const response = await apiFetch("/api/my-files/?file_type=summary");
      if (!response.ok) {
        setListError("Couldn't load your summaries. Please refresh to try again.");
        return;
      }
      const data = await response.json();
      const items = (data.projects || []).map((project) => ({
        id: project.schema_name || project.id,
        name: project.schema_name || String(project.id),
        display_name:
          project.display_name || project.schema_name || String(project.id),
        description: project.description || "",
      }));
      setAvailable(items);
      if (!preselect || appliedPreselectRef.current === preselect) return;
      appliedPreselectRef.current = preselect;
      setSelected(preselect);
      const match = items.find((item) => item.id === preselect);
      if (match) setSelectedName(match.display_name || match.name);
    } catch (fetchError) {
      console.error("Error fetching summaries:", fetchError);
      setListError("Couldn't reach the server to load your summaries. Check your connection and refresh.");
    } finally {
      setListLoading(false);
    }
  }, [preselect, projectsList, selectedProject]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    fetchAvailableSummaries();
  }, [fetchAvailableSummaries]);

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
    apiFetch(`/api/summary/${encodeURIComponent(selected)}`)
      .then((response) => {
        if (!mounted) return null;
        if (!response.ok) {
          throw new Error(
            response.status === 404
              ? "This summary no longer exists."
              : `Couldn't load this summary (HTTP ${response.status}).`,
          );
        }
        return response.json();
      })
      .then((data) => {
        if (!mounted || !data) return;
        const summary = data.summary || data || {};
        // The JSON fallback is fenced rather than handed to the markdown
        // renderer raw: its 4-space indentation would otherwise be parsed as
        // a chain of indented code blocks and rendered as garbage.
        const fallback = ["```json", JSON.stringify(summary, null, 2), "```"].join("\n");
        setContent(summary.content || summary.summary || fallback);
        setSelectedName(summary.display_name || summary.name || selected);
      })
      .catch((fetchError) => {
        if (!mounted) return;
        setError(fetchError.message || "Failed to load summary");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [selected]);

  return {
    available,
    projectsList,
    selectedProject,
    setSelectedProject,
    selected,
    setSelected,
    selectedName,
    content,
    loading,
    error,
    listError,
    listLoading,
  };
}
