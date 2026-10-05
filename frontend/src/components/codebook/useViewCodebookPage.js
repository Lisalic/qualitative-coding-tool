import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch, requestJson } from "../../api";
import { cloneCodebookTree, flattenTreeToCodes, groupCodesByFamily } from "../../lib/codingUtils";
import DialogService from "../feedback/DialogService";
import { useLeaveGuard } from "../feedback/LeaveGuard";
import { useRefParam } from "../primitives/useRefParam";

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
  const selectedCodebookRef = useRef(selectedCodebook);
  selectedCodebookRef.current = selectedCodebook;
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [codebookTree, setCodebookTree] = useState([]);
  const [selectedCodebookName, setSelectedCodebookName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [instructions, setInstructions] = useState("");
  const [promptMeta, setPromptMeta] = useState(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [codebookDraft, setCodebookDraft] = useState([]);
  const [saveState, setSaveState] = useState({ status: "idle", message: "" });
  const [refreshKey, setRefreshKey] = useState(0);
  // The codebook list refetches for reasons unrelated to the initial
  // "view" navigation (e.g. once the project list finishes loading in),
  // and each refetch used to unconditionally re-apply the location.state
  // preselection -- which silently snapped the selection back even after
  // the user had since clicked a different codebook. Track which
  // preselect value has already been applied so it's only ever consumed
  // once per distinct navigation, not once per refetch.
  const appliedPreselectRef = useRef(null);
  const [listError, setListError] = useState("");
  const [listLoading, setListLoading] = useState(false);

  // The open codebook lives in the URL as `?ref=<schema>` (refresh and
  // Back keep it); a link's `location.state.selected` still wins.
  const selectedSchema =
    availableCodebooks.find((codebook) => String(codebook.id) === String(selectedCodebook))?.metadata
      ?.schema || null;
  const urlRef = useRefParam(selectedSchema);
  const preselected = location?.state?.selected || urlRef;

  // Edit mode holds an unsaved draft of the whole codebook.
  useLeaveGuard(isEditMode);

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
    setListError("");
    setListLoading(true);
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

      if (preselected && appliedPreselectRef.current !== preselected) {
        const selected = codebooks.find((cb) => matchesPreselection(cb, preselected));
        if (selected) {
          appliedPreselectRef.current = preselected;
          setSelectedCodebook(String(selected.id));
          setSelectedCodebookName(
            selected?.display_name || selected?.name || selected?.id || "",
          );
        }
      }
    } catch (fetchError) {
      console.error("Error fetching codebooks list:", fetchError);
      setListError("Couldn't load your codebooks. Check your connection and refresh to try again.");
    } finally {
      setListLoading(false);
    }
  }, [preselected, projectsList, selectedProject]);

  // Switching codebooks quickly can leave an older request in flight; only
  // the newest may fill the tree, or editing and saving the codebook on
  // screen would write the previous codebook's codes into it.
  const latestCodebookRequest = useRef(0);
  const fetchCodebook = useCallback(async (codebookId) => {
    const requestId = ++latestCodebookRequest.current;
    const isCurrent = () =>
      requestId === latestCodebookRequest.current && String(codebookId) === String(selectedCodebookRef.current);
    try {
      setLoading(true);
      setError(null);
      const response = await apiFetch(`/api/codebook?codebook_id=${codebookId}`);
      if (!response.ok) throw new Error("Failed to fetch codebook");
      const data = await response.json();
      if (!isCurrent()) return;
      setCodebookTree(groupCodesByFamily(data.codes));
      setSystemPrompt(data.systemprompt || "");
      setInstructions(data.instructions || "");
      setPromptMeta(data.prompt_meta || null);
    } catch (fetchError) {
      if (isCurrent()) setError(fetchError.message);
    } finally {
      if (isCurrent()) setLoading(false);
    }
  }, []);

  const beginEdit = useCallback(() => {
    setCodebookDraft(cloneCodebookTree(codebookTree));
    setIsEditMode(true);
    setSaveState({ status: "idle", message: "" });
  }, [codebookTree]);

  const cancelEdit = useCallback(() => {
    setIsEditMode(false);
    setCodebookDraft([]);
    setSaveState({ status: "idle", message: "" });
  }, []);

  const changeSelectedCodebook = useCallback(async (codebookId) => {
    if (
      isEditMode &&
      !(await DialogService.confirm("You have unsaved codebook edits. Switch codebooks and discard them?", {
        title: "Unsaved changes",
        confirmLabel: "Discard edits",
        danger: true,
      }))
    ) {
      return;
    }
    selectedCodebookRef.current = codebookId;
    setSelectedCodebook(codebookId);
    setIsEditMode(false);
    setCodebookDraft([]);
    setSaveState({ status: "idle", message: "" });
  }, [isEditMode]);

  const saveEdit = useCallback(
    async (displayName) => {
      if (!selectedCodebook) {
        setSaveState({ status: "error", message: "No codebook selected." });
        return;
      }
      setSaveState({ status: "saving", message: "Saving…" });
      const codes = flattenTreeToCodes(codebookDraft);
      const result = await requestJson(`/api/codebook/${encodeURIComponent(selectedCodebook)}`, {
        method: "PUT",
        body: { codes, display_name: displayName },
      });
      if (String(selectedCodebookRef.current) !== String(selectedCodebook)) return;
      if (!result.ok) {
        setSaveState({ status: "error", message: result.error || "Failed to save codebook." });
        return;
      }
      setIsEditMode(false);
      setCodebookDraft([]);
      setSaveState({ status: "success", message: "Saved." });
      setRefreshKey((key) => key + 1);
      await fetchCodebook(selectedCodebook);
      await fetchAvailableCodebooks();
    },
    [selectedCodebook, codebookDraft, fetchCodebook, fetchAvailableCodebooks],
  );

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    fetchAvailableCodebooks();
  }, [fetchAvailableCodebooks]);

  useEffect(() => {
    if (!selectedCodebook) return;
    fetchCodebook(selectedCodebook);
  }, [fetchCodebook, selectedCodebook]);

  useEffect(() => {
    const selected = availableCodebooks.find(
      (codebook) => String(codebook.id) === String(selectedCodebook),
    );
    if (!selected) return;
    setSelectedCodebookName(
      selected.display_name || selected.name || selected.id || "",
    );
  }, [availableCodebooks, selectedCodebook]);

  return {
    availableCodebooks,
    selectedCodebook,
    setSelectedCodebook: changeSelectedCodebook,
    projectsList,
    selectedProject,
    setSelectedProject,
    codebookTree,
    selectedCodebookName,
    loading,
    error,
    listError,
    listLoading,
    systemPrompt,
    instructions,
    promptMeta,
    isEditMode,
    codebookDraft,
    setCodebookDraft,
    saveState,
    beginEdit,
    cancelEdit,
    saveEdit,
    refreshKey,
    refetchCodebook: () => selectedCodebook && fetchCodebook(selectedCodebook),
  };
}
