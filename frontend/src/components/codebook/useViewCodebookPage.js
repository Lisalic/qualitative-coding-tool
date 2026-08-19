import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../../api";

function matchesPreselection(item, value) {
  return (
    String(item.id) === String(value) ||
    item.metadata?.schema === value ||
    item.display_name === value ||
    item.name === value
  );
}

export default function useViewCodebookPage() {
  const location = useLocation();
  const [availableCodebooks, setAvailableCodebooks] = useState([]);
  const [selectedCodebook, setSelectedCodebook] = useState(null);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [codebookContent, setCodebookContent] = useState("");
  const [selectedCodebookName, setSelectedCodebookName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState("tree");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  // The codebook list refetches for reasons unrelated to the initial
  // "view" navigation (e.g. once the project list finishes loading in),
  // and each refetch used to unconditionally re-apply the location.state
  // preselection -- which silently snapped the selection back even after
  // the user had since clicked a different codebook. Track which
  // preselect value has already been applied so it's only ever consumed
  // once per distinct navigation, not once per refetch.
  const appliedPreselectRef = useRef(null);

  const fetchProjects = useCallback(async () => {
    try {
      const resp = await apiFetch("/api/projects/");
      if (!resp.ok) return;
      const data = await resp.json();
      setProjectsList(data.projects || []);
    } catch (fetchError) {
      console.error("Error fetching projects:", fetchError);
    }
  }, []);

  const fetchAvailableCodebooks = useCallback(async () => {
    try {
      if (projectsList.length > 0 && selectedProject) {
        const projectObj = projectsList.find(
          (project) => String(project.id) === String(selectedProject),
        );
        const files = (projectObj && projectObj.files) || [];
        const codebookFiles = files
          .filter((file) => file.file_type === "codebook")
          .map((file) => ({
            id: String(file.id),
            display_name: file.display_name || file.schema_name || String(file.id),
            description: file.description || null,
            metadata: { schema: file.schema_name, file },
          }));
        setAvailableCodebooks(codebookFiles);

        const preselected = location?.state?.selected;
        if (!preselected || appliedPreselectRef.current === preselected) return;
        const match = codebookFiles.find((item) => matchesPreselection(item, preselected));
        if (!match) return;
        appliedPreselectRef.current = preselected;
        setSelectedCodebook(match.id);
        setSelectedCodebookName(match.display_name || match.name || match.id || "");
        return;
      }

      const response = await apiFetch("/api/list-codebooks");
      if (!response.ok) throw new Error("Failed to fetch codebooks list");

      const data = await response.json();
      const codebooks = Array.isArray(data.codebooks) ? data.codebooks : [];
      setAvailableCodebooks(codebooks);
      if (codebooks.length === 0) return;

      const preselected = location?.state?.selected;
      if (preselected && appliedPreselectRef.current !== preselected) {
        const selected = codebooks.find((cb) => matchesPreselection(cb, preselected));
        if (selected) {
          appliedPreselectRef.current = preselected;
          setSelectedCodebook(String(selected.id));
          setSelectedCodebookName(
            selected?.display_name || selected?.name || selected?.id || "",
          );
          return;
        }
      }

      if (appliedPreselectRef.current !== null) return;
      const urlParams = new URLSearchParams(window.location.search);
      const selectedFromUrl = urlParams.get("selected");
      if (selectedFromUrl) {
        const selected = codebooks.find((cb) => matchesPreselection(cb, selectedFromUrl));
        if (selected) {
          appliedPreselectRef.current = selectedFromUrl;
          setSelectedCodebook(String(selected.id));
          setSelectedCodebookName(
            selected?.display_name || selected?.name || selected?.id || "",
          );
        }
      }
    } catch (fetchError) {
      console.error("Error fetching codebooks list:", fetchError);
    }
  }, [location?.state?.selected, projectsList, selectedProject]);

  const fetchCodebook = useCallback(async (codebookId) => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiFetch(`/api/codebook?codebook_id=${codebookId}`);
      if (!response.ok) throw new Error("Failed to fetch codebook");
      const data = await response.json();
      if (!data.codebook) {
        setCodebookContent("");
        setSystemPrompt("");
        setUserPrompt("");
        return;
      }
      setCodebookContent(data.codebook);
      setSystemPrompt(data.systemprompt || "");
      setUserPrompt(data.userprompt || "");
    } catch (fetchError) {
      setError(fetchError.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSelectionChangeAfterSave = useCallback(
    (resp) => {
      if (typeof resp === "string") {
        if (resp !== selectedCodebook) {
          setSelectedCodebook(resp);
          fetchAvailableCodebooks();
        }
      } else if (resp && resp.display_name) {
        setSelectedCodebookName(resp.display_name);
        fetchAvailableCodebooks();
      }
    },
    [fetchAvailableCodebooks, selectedCodebook],
  );

  useEffect(() => {
    fetchAvailableCodebooks();
    fetchProjects();
  }, [fetchAvailableCodebooks, fetchProjects]);

  useEffect(() => {
    if (!selectedCodebook) return;
    fetchCodebook(selectedCodebook);
    const selected = availableCodebooks.find(
      (codebook) => String(codebook.id) === String(selectedCodebook),
    );
    setSelectedCodebookName(
      selected?.display_name || selected?.name || selected?.id || "",
    );
  }, [availableCodebooks, fetchCodebook, selectedCodebook]);

  return {
    availableCodebooks,
    selectedCodebook,
    setSelectedCodebook,
    projectsList,
    selectedProject,
    setSelectedProject,
    codebookContent,
    selectedCodebookName,
    loading,
    error,
    viewMode,
    setViewMode,
    systemPrompt,
    userPrompt,
    handleSelectionChangeAfterSave,
  };
}
