import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../../../api";
import {
  cloneCodebookTree,
  formatCodingData,
  parseCodingData,
  serializeCodebookTreeToText,
} from "../../../lib/codingUtils";
import {
  cloneParsedCodingRows,
  extractApiErrorMessage,
  normalizeParsedCodingRows,
} from "../../../lib/codingViewHelpers";

export default function useViewCodingPage() {
  const location = useLocation();
  const [availableCodedData, setAvailableCodedData] = useState([]);
  const [selectedCodedData, setSelectedCodedData] = useState(null);
  const [selectedCodedDataName, setSelectedCodedDataName] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [codedDataContent, setCodedDataContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [parsedCoding, setParsedCoding] = useState([]);
  const [codebookTree, setCodebookTree] = useState([]);
  const [postContents, setPostContents] = useState({});
  const [viewMode, setViewMode] = useState("table");
  const [selectedFilterCodes, setSelectedFilterCodes] = useState([]);
  const [tableSaveState, setTableSaveState] = useState({
    status: "idle",
    message: "",
  });
  const [isTableEditMode, setIsTableEditMode] = useState(false);
  const [tableDraftParsedCoding, setTableDraftParsedCoding] = useState([]);
  const [tableDraftCodebookTree, setTableDraftCodebookTree] = useState([]);
  const [tableEditName, setTableEditName] = useState("");
  // The coded-data list refetches for reasons unrelated to the initial
  // "view" navigation (e.g. once the project list finishes loading in),
  // and each refetch used to unconditionally re-apply the location.state
  // preselection -- which silently snapped the selection back even after
  // the user had since clicked a different coding. Track which preselect
  // value has already been applied so it's only ever consumed once per
  // distinct navigation, not once per refetch.
  const appliedPreselectRef = useRef(null);

  const fetchProjects = useCallback(async () => {
    try {
      const resp = await apiFetch("/api/projects/", { cache: "no-cache" });
      if (!resp.ok) return;
      const data = await resp.json();
      const projects = data.projects || [];
      setProjectsList(projects);
      if (!selectedProject) setSelectedProject("");
    } catch (error) {
      console.error("Error fetching projects:", error);
    }
  }, [selectedProject]);

  const fetchAvailableCodedData = useCallback(async () => {
    try {
      if (projectsList.length > 0 && selectedProject) {
        const projectObj = projectsList.find(
          (project) => String(project.id) === String(selectedProject),
        );
        const files = (projectObj && projectObj.files) || [];
        const codingFiles = files
          .filter((file) => file.file_type === "coding")
          .map((file) => ({
            id: file.schema_name || String(file.id),
            name: file.display_name || file.schema_name || String(file.id),
            display_name: file.display_name,
            description: file.description || null,
            metadata: { schema: file.schema_name, file },
            source: "project",
          }));
        setAvailableCodedData(codingFiles);

        const preselected = location?.state?.selectedCodedData;
        if (preselected && appliedPreselectRef.current !== preselected) {
          const match = codingFiles.find(
            (item) =>
              String(item.id) === String(preselected) ||
              String(item?.metadata?.file?.id) === String(preselected),
          );
          if (match) {
            appliedPreselectRef.current = preselected;
            setSelectedCodedData(match.id);
            setSelectedCodedDataName(
              match?.display_name || match?.name || match?.id || "",
            );
          }
        }
        return;
      }

      const resp = await apiFetch("/api/my-files/?file_type=coding");
      if (!resp.ok) {
        console.warn("Failed to fetch coded data list; no coded data available");
        setAvailableCodedData([]);
        setSelectedCodedData(null);
        setSelectedCodedDataName("");
        return;
      }

      const json = await resp.json();
      const items = (json.projects || []).map((project) => ({
        id: project.schema_name || project.id,
        name: project.display_name || project.schema_name || project.id,
        display_name: project.display_name,
        description: project.description || null,
        metadata: { schema: project.schema_name, file: project },
        source: "project",
      }));
      setAvailableCodedData(items);

      const preselected = location?.state?.selectedCodedData;
      if (!preselected || appliedPreselectRef.current === preselected) return;
      const match = items.find((item) => item.id === preselected);
      if (!match) return;
      appliedPreselectRef.current = preselected;
      setSelectedCodedData(match.id);
      setSelectedCodedDataName(match?.display_name || match?.name || match?.id || "");
    } catch (error) {
      console.error("Error fetching coded data list:", error);
    }
  }, [location?.state?.selectedCodedData, projectsList, selectedProject]);

  const fetchCodedData = useCallback(async (codedDataId) => {
    try {
      setLoading(true);
      const response = await apiFetch(`/api/coded-data?coded_id=${codedDataId}`);
      if (!response.ok) throw new Error("Failed to fetch coded data");
      const data = await response.json();
      if (!data.coded_data) {
        setCodedDataContent("");
        setCodebookTree([]);
        setSystemPrompt("");
        setUserPrompt("");
        return;
      }
      setCodedDataContent(data.coded_data);
      setCodebookTree(Array.isArray(data.codebook_tree) ? data.codebook_tree : []);
      setSystemPrompt(data.systemprompt || "");
      setUserPrompt(data.userprompt || "");
    } catch (error) {
      console.error("Error fetching coded data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchPostContents = useCallback(
    async (codedDataId) => {
      try {
        const selectedFile = availableCodedData.find(
          (file) => file.id === codedDataId,
        );
        if (!selectedFile?.metadata?.file?.parent_files) return;

        const parentDb = selectedFile.metadata.file.parent_files.find(
          (parent) => parent.type === "raw_data" || parent.type === "filtered_data",
        );
        if (!parentDb) return;

        const schemaName =
          parentDb.schema_name ||
          (parentDb.name && parentDb.name.startsWith("proj_") ? parentDb.name : null);
        if (!schemaName) return;

        const postIds = [...new Set(parsedCoding.map((post) => post.postId))];
        if (postIds.length === 0) return;

        const resp = await apiFetch("/api/post-contents/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ schema: schemaName, post_ids: postIds }),
          cache: "no-cache",
        });
        if (!resp.ok) return;

        const data = await resp.json();
        setPostContents(data.contents || {});
      } catch (error) {
        console.error("Error fetching post contents:", error);
      }
    },
    [availableCodedData, parsedCoding],
  );

  const getSelectedCodingSchema = useCallback(
    (codedId = selectedCodedData) => {
      const selectedItem = availableCodedData.find(
        (item) => String(item.id) === String(codedId),
      );
      const schemaFromMetadata = selectedItem?.metadata?.schema;
      if (schemaFromMetadata) return schemaFromMetadata;
      if (typeof codedId === "string" && codedId.startsWith("proj_")) return codedId;
      return null;
    },
    [availableCodedData, selectedCodedData],
  );

  const beginTableEditMode = useCallback(() => {
    setTableDraftParsedCoding(cloneParsedCodingRows(parsedCoding));
    setTableDraftCodebookTree(cloneCodebookTree(codebookTree));
    setTableEditName(selectedCodedDataName || selectedCodedData || "");
    setTableSaveState({ status: "idle", message: "" });
    setIsTableEditMode(true);
  }, [codebookTree, parsedCoding, selectedCodedData, selectedCodedDataName]);

  const cancelTableEditMode = useCallback(() => {
    setIsTableEditMode(false);
    setTableDraftParsedCoding([]);
    setTableDraftCodebookTree([]);
    setTableEditName(selectedCodedDataName || "");
    setTableSaveState({ status: "idle", message: "" });
  }, [selectedCodedDataName]);

  const propagateCodingRowCodeRename = useCallback((oldName, newName) => {
    if (!oldName || !newName || oldName === newName) return;
    setTableDraftParsedCoding((rows) =>
      (Array.isArray(rows) ? rows : []).map((row) => ({
        ...row,
        codeEvidence: (Array.isArray(row?.codeEvidence) ? row.codeEvidence : []).map(
          (entry) =>
            String(entry?.code || "").trim() === oldName
              ? { ...entry, code: newName }
              : entry,
        ),
      })),
    );
  }, []);

  const prepareTableSavePayload = useCallback(() => {
    const trimmedName = String(tableEditName || "").trim();
    if (!trimmedName) return { ok: false, error: "Name is required." };

    const normalizeResult = normalizeParsedCodingRows(tableDraftParsedCoding);
    if (!normalizeResult.ok) return normalizeResult;

    const formattedContent = formatCodingData(normalizeResult.rows);
    if (!formattedContent) {
      return { ok: false, error: "Cannot save an empty coding table." };
    }

    const codebookText = serializeCodebookTreeToText(
      Array.isArray(tableDraftCodebookTree) ? tableDraftCodebookTree : [],
    );

    return {
      ok: true,
      name: trimmedName,
      rows: normalizeResult.rows,
      formattedContent,
      codebookText,
    };
  }, [tableDraftCodebookTree, tableDraftParsedCoding, tableEditName]);

  const handleTableSaveOverwrite = useCallback(async () => {
    const schemaName = getSelectedCodingSchema();
    if (!schemaName) {
      setTableSaveState({
        status: "error",
        message: "Unable to resolve coding schema for overwrite.",
      });
      return;
    }

    const payload = prepareTableSavePayload();
    if (!payload.ok) {
      setTableSaveState({
        status: "error",
        message: payload.error || "Unable to prepare coding data for save.",
      });
      return;
    }

    setTableSaveState({
      status: "saving",
      message: "Saving and overwriting current schema...",
    });

    try {
      const formData = new FormData();
      formData.append("schema_name", schemaName);
      formData.append("content", payload.formattedContent);
      formData.append("display_name", payload.name);
      formData.append("codebook_text", payload.codebookText ?? "");

      const response = await apiFetch("/api/save-file-coded-data/", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const message = await extractApiErrorMessage(
          response,
          "Failed to save and overwrite coding data.",
        );
        setTableSaveState({ status: "error", message });
        return;
      }

      setCodedDataContent(payload.formattedContent);
      setParsedCoding(payload.rows);
      setCodebookTree(cloneCodebookTree(tableDraftCodebookTree));
      setSelectedCodedDataName(payload.name);
      setIsTableEditMode(false);
      setTableDraftParsedCoding([]);
      setTableDraftCodebookTree([]);
      setTableEditName(payload.name);
      setTableSaveState({
        status: "success",
        message: "Saved and overwrote current schema.",
      });
      fetchAvailableCodedData();
    } catch (error) {
      setTableSaveState({
        status: "error",
        message: error?.message || "Failed to save and overwrite coding data.",
      });
    }
  }, [
    fetchAvailableCodedData,
    getSelectedCodingSchema,
    prepareTableSavePayload,
    tableDraftCodebookTree,
  ]);

  const handleTableSaveDuplicate = useCallback(async () => {
    const schemaName = getSelectedCodingSchema();
    if (!schemaName) {
      setTableSaveState({
        status: "error",
        message: "Unable to resolve coding schema for duplicate save.",
      });
      return;
    }

    const payload = prepareTableSavePayload();
    if (!payload.ok) {
      setTableSaveState({
        status: "error",
        message: payload.error || "Unable to prepare coding data for save.",
      });
      return;
    }

    setTableSaveState({
      status: "saving",
      message: "Saving and duplicating into a new schema...",
    });

    try {
      const formData = new FormData();
      formData.append("source_schema_name", schemaName);
      formData.append("content", payload.formattedContent);
      formData.append("display_name", payload.name);
      formData.append("codebook_text", payload.codebookText ?? "");

      const response = await apiFetch("/api/save-file-coded-data-duplicate/", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const message = await extractApiErrorMessage(
          response,
          "Failed to save and duplicate coding data.",
        );
        setTableSaveState({ status: "error", message });
        return;
      }

      let responsePayload = null;
      try {
        responsePayload = await response.json();
      } catch {
        responsePayload = null;
      }

      const savedCodebookTree = cloneCodebookTree(tableDraftCodebookTree);
      setIsTableEditMode(false);
      setTableDraftParsedCoding([]);
      setTableDraftCodebookTree([]);
      setTableEditName(selectedCodedDataName || "");
      setTableSaveState({
        status: "success",
        message: `Saved and duplicated as ${responsePayload?.filename || payload.name}.`,
      });
      fetchAvailableCodedData();

      if (!responsePayload?.schema_name) return;
      setSelectedCodedData(responsePayload.schema_name);
      setSelectedCodedDataName(responsePayload.filename || payload.name || "");
      setCodedDataContent(payload.formattedContent);
      setParsedCoding(payload.rows);
      setCodebookTree(savedCodebookTree);
    } catch (error) {
      setTableSaveState({
        status: "error",
        message: error?.message || "Failed to save and duplicate coding data.",
      });
    }
  }, [
    fetchAvailableCodedData,
    getSelectedCodingSchema,
    prepareTableSavePayload,
    selectedCodedDataName,
    tableDraftCodebookTree,
  ]);

  const handleCodedDataChange = useCallback(
    (codedDataId) => {
      setSelectedCodedData(codedDataId);
      const selected = availableCodedData.find((item) => item.id === codedDataId);
      setSelectedCodedDataName(
        selected?.display_name || selected?.name || codedDataId || "",
      );
    },
    [availableCodedData],
  );

  const handleMarkdownSaved = useCallback(
    (resp) => {
      if (typeof resp === "string") {
        if (resp !== selectedCodedData) {
          setSelectedCodedData(resp);
          fetchAvailableCodedData();
        }
      } else if (resp && resp.display_name) {
        setSelectedCodedDataName(resp.display_name);
        fetchAvailableCodedData();
      }
      setRefreshKey((key) => key + 1);
    },
    [fetchAvailableCodedData, selectedCodedData],
  );

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    fetchAvailableCodedData();
  }, [fetchAvailableCodedData]);

  useEffect(() => {
    if (selectedCodedData) fetchCodedData(selectedCodedData);
  }, [fetchCodedData, selectedCodedData]);

  useEffect(() => {
    setCodedDataContent("");
    setCodebookTree([]);
    setSystemPrompt("");
    setUserPrompt("");
    setParsedCoding([]);
    setIsTableEditMode(false);
    setTableDraftParsedCoding([]);
    setTableDraftCodebookTree([]);
    setTableEditName("");
    setPostContents({});
    setSelectedFilterCodes([]);
    setTableSaveState({ status: "idle", message: "" });
  }, [selectedCodedData]);

  useEffect(() => {
    if (isTableEditMode) return;
    setTableEditName(selectedCodedDataName || "");
  }, [isTableEditMode, selectedCodedDataName]);

  useEffect(() => {
    if (viewMode === "table") return;
    if (!isTableEditMode) return;
    setIsTableEditMode(false);
    setTableDraftParsedCoding([]);
    setTableDraftCodebookTree([]);
    setTableEditName(selectedCodedDataName || "");
    setTableSaveState({ status: "idle", message: "" });
  }, [isTableEditMode, selectedCodedDataName, viewMode]);

  useEffect(() => {
    if (tableSaveState.status !== "success") return;
    const timeoutId = setTimeout(() => {
      setTableSaveState((prev) =>
        prev.status === "success" ? { status: "idle", message: "" } : prev,
      );
    }, 2400);
    return () => clearTimeout(timeoutId);
  }, [tableSaveState.status]);

  useEffect(() => {
    if (codedDataContent && selectedCodedData) {
      setParsedCoding(parseCodingData(codedDataContent));
    }
  }, [codedDataContent, selectedCodedData]);

  useEffect(() => {
    if (parsedCoding.length > 0 && selectedCodedData) {
      fetchPostContents(selectedCodedData);
    }
  }, [fetchPostContents, parsedCoding, selectedCodedData]);

  const selectedCodingSchema = getSelectedCodingSchema();
  const selectedCodingDescription = availableCodedData.find(
    (codedData) => codedData.id === selectedCodedData,
  )?.description;

  return {
    availableCodedData,
    selectedCodedData,
    selectedCodedDataName,
    refreshKey,
    projectsList,
    selectedProject,
    setSelectedProject,
    systemPrompt,
    userPrompt,
    loading,
    parsedCoding,
    codebookTree,
    postContents,
    viewMode,
    setViewMode,
    selectedFilterCodes,
    setSelectedFilterCodes,
    tableSaveState,
    isTableEditMode,
    tableDraftParsedCoding,
    setTableDraftParsedCoding,
    tableDraftCodebookTree,
    setTableDraftCodebookTree,
    tableEditName,
    setTableEditName,
    selectedCodingSchema,
    selectedCodingDescription,
    beginTableEditMode,
    cancelTableEditMode,
    propagateCodingRowCodeRename,
    handleTableSaveOverwrite,
    handleTableSaveDuplicate,
    handleCodedDataChange,
    handleMarkdownSaved,
  };
}
