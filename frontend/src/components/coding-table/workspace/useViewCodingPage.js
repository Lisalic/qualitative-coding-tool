import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch, postJsonAndPoll, requestJson } from "../../../api";
import { buildRecodeItemsPayload, MissingFieldsError } from "../../../lib/apiContracts";
import { cloneCodebookTree, serializeCodebookTreeToText } from "../../../lib/codingUtils";
import { normalizeCodingRowEdits } from "../../../lib/codingViewHelpers";

const ROWS_PER_PAGE = 25;
const SEARCH_DEBOUNCE_MS = 400;

/**
 * Backs the 3-pane View Coding workspace (document list / reader pane /
 * codebook sidebar) -- see CodingWorkspaceSection.jsx. Tagging is
 * auto-saved per action (select text, click a code -> immediately
 * PUT /api/coding/{ref}/rows for just that one row) rather than staged
 * into a page-wide draft and saved all at once; this mirrors how a real
 * coding tool behaves and means there is no separate "edit mode" for
 * rows any more -- only the codebook (rename/add/remove families and
 * codes) still has an explicit edit/save step, since that's a batch of
 * related changes a researcher composes before committing.
 */
export default function useViewCodingPage() {
  const location = useLocation();
  const [availableCodedData, setAvailableCodedData] = useState([]);
  const [selectedCodedData, setSelectedCodedData] = useState(null);
  const [selectedCodedDataName, setSelectedCodedDataName] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const appliedPreselectRef = useRef(null);

  // Artifact metadata: GET /api/coding/{ref}
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [codebookTree, setCodebookTree] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [totalCoded, setTotalCoded] = useState(0);
  const [artifactLoading, setArtifactLoading] = useState(false);

  // Rows: GET /api/coding/{ref}/rows
  const [rows, setRows] = useState([]);
  const [rowsTotal, setRowsTotal] = useState(0);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [onlyFilter, setOnlyFilter] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilterCode, setActiveFilterCode] = useState(null);

  const [viewMode, setViewMode] = useState("reader");
  const [activeItemId, setActiveItemId] = useState(null);
  const [pendingSelection, setPendingSelection] = useState(null);
  const [selectedItemIds, setSelectedItemIds] = useState(() => new Set());
  const [rowActionError, setRowActionError] = useState(null);

  const [isCodebookEditMode, setIsCodebookEditMode] = useState(false);
  const [codebookDraft, setCodebookDraft] = useState([]);
  const [codebookSaveState, setCodebookSaveState] = useState({ status: "idle", message: "" });

  const [recodeModel, setRecodeModel] = useState("");
  const [recodeMethodology, setRecodeMethodology] = useState("");
  const [recodeLoading, setRecodeLoading] = useState(false);
  const [recodeProgress, setRecodeProgress] = useState(null);
  const [recodeError, setRecodeError] = useState(null);
  const [recodeSummary, setRecodeSummary] = useState("");

  const fetchProjects = useCallback(async () => {
    try {
      const resp = await apiFetch("/api/projects/", { cache: "no-cache" });
      if (!resp.ok) return;
      const data = await resp.json();
      setProjectsList(data.projects || []);
    } catch (error) {
      console.error("Error fetching projects:", error);
    }
  }, []);

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
            setSelectedCodedDataName(match?.display_name || match?.name || match?.id || "");
          }
        }
        return;
      }

      const resp = await apiFetch("/api/my-files/?file_type=coding");
      if (!resp.ok) {
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

  const getSelectedCodingSchema = useCallback(
    (codedId = selectedCodedData) => {
      const selectedItem = availableCodedData.find((item) => String(item.id) === String(codedId));
      const schemaFromMetadata = selectedItem?.metadata?.schema;
      if (schemaFromMetadata) return schemaFromMetadata;
      if (typeof codedId === "string" && codedId.startsWith("proj_")) return codedId;
      return null;
    },
    [availableCodedData, selectedCodedData],
  );

  const fetchCodingArtifact = useCallback(async (schema) => {
    setArtifactLoading(true);
    const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}`, { method: "GET" });
    setArtifactLoading(false);
    if (!result.ok) {
      setCodebookTree([]);
      setSystemPrompt("");
      setUserPrompt("");
      setTotalRows(0);
      setTotalCoded(0);
      return;
    }
    setCodebookTree(Array.isArray(result.data.codebook_tree) ? result.data.codebook_tree : []);
    setSystemPrompt(result.data.file?.systemprompt || "");
    setUserPrompt(result.data.file?.userprompt || "");
    setTotalRows(result.data.total_rows || 0);
    setTotalCoded(result.data.total_coded || 0);
  }, []);

  const fetchCodingRows = useCallback(
    async (schema, { page: pageArg, only, q, code } = {}) => {
      setRowsLoading(true);
      const params = new URLSearchParams({
        limit: String(ROWS_PER_PAGE),
        offset: String((pageArg || 0) * ROWS_PER_PAGE),
        only: only || "all",
      });
      if (q) params.set("q", q);
      if (code) params.set("code", code);
      const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}/rows?${params}`, {
        method: "GET",
      });
      setRowsLoading(false);
      if (!result.ok) {
        setRows([]);
        setRowsTotal(0);
        return;
      }
      const nextRows = Array.isArray(result.data.rows) ? result.data.rows : [];
      setRows(nextRows);
      setRowsTotal(result.data.total || 0);
      setActiveItemId((prev) => {
        if (prev && nextRows.some((row) => row.item_id === prev)) return prev;
        return nextRows[0]?.item_id ?? null;
      });
    },
    [],
  );

  const refreshCurrent = useCallback(() => {
    const schema = getSelectedCodingSchema();
    if (!schema) return;
    fetchCodingArtifact(schema);
    fetchCodingRows(schema, { page, only: onlyFilter, q: searchQuery, code: activeFilterCode });
  }, [
    getSelectedCodingSchema,
    fetchCodingArtifact,
    fetchCodingRows,
    page,
    onlyFilter,
    searchQuery,
    activeFilterCode,
  ]);

  // ---------------------------------------------------------------------
  // Row tagging -- auto-saved per action. Every mutation replaces exactly
  // one row's coding via PUT /api/coding/{ref}/rows (a single-row array),
  // then patches local state so the reader/list update instantly without
  // a full page refetch.
  // ---------------------------------------------------------------------

  const putRowEntries = useCallback(
    async (itemId, entries) => {
      const schema = getSelectedCodingSchema();
      if (!schema) {
        setRowActionError("Unable to resolve coding schema.");
        return false;
      }
      const normalized = normalizeCodingRowEdits([{ itemId, codes: entries }]);
      if (!normalized.ok) {
        setRowActionError(normalized.error);
        return false;
      }
      const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}/rows`, {
        method: "PUT",
        body: { rows: normalized.rows },
      });
      if (!result.ok) {
        setRowActionError(result.error || "Failed to save coding.");
        return false;
      }
      setRowActionError(null);
      setRows((prev) =>
        prev.map((row) => (row.item_id === itemId ? { ...row, codes: entries } : row)),
      );
      fetchCodingArtifact(schema);
      return true;
    },
    [fetchCodingArtifact, getSelectedCodingSchema],
  );

  const activeRow = useMemo(
    () => rows.find((row) => row.item_id === activeItemId) || null,
    [rows, activeItemId],
  );

  // Stable identity (no deps) so the effect in HighlightedContent that
  // reports selection changes up to here doesn't see a new function on
  // every render -- an unstable callback there previously created a
  // feedback loop: new callback -> effect re-fires -> setPendingSelection
  // with a new object -> re-render -> new callback -> ... forever.
  // `selection` is `{ text, start, end }` (offsets computed directly from
  // the real DOM range in HighlightedContent -- see its module comment)
  // or `null` when the selection is cleared.
  const handleSelectionChange = useCallback((selection) => {
    setPendingSelection((prev) => {
      if (!selection) return prev === null ? prev : null;
      if (prev && prev.text === selection.text && prev.start === selection.start && prev.end === selection.end) {
        return prev;
      }
      return selection;
    });
  }, []);

  const applyCodeToSelection = useCallback(
    async (code) => {
      if (!activeRow || !pendingSelection?.text || !code) return;
      const entries = [
        ...(Array.isArray(activeRow.codes) ? activeRow.codes : []),
        {
          code,
          quote: pendingSelection.text,
          start_offset: pendingSelection.start,
          end_offset: pendingSelection.end,
          notes: null,
        },
      ];
      const ok = await putRowEntries(activeRow.item_id, entries);
      if (ok) setPendingSelection(null);
    },
    [activeRow, pendingSelection, putRowEntries],
  );

  const removeCodeEntry = useCallback(
    async (entryIndex) => {
      if (!activeRow) return;
      const entries = (Array.isArray(activeRow.codes) ? activeRow.codes : []).filter(
        (_, idx) => idx !== entryIndex,
      );
      await putRowEntries(activeRow.item_id, entries);
    },
    [activeRow, putRowEntries],
  );

  const updateEntryNotes = useCallback(
    async (entryIndex, notes) => {
      if (!activeRow) return;
      const entries = (Array.isArray(activeRow.codes) ? activeRow.codes : []).map((entry, idx) =>
        idx === entryIndex ? { ...entry, notes } : entry,
      );
      await putRowEntries(activeRow.item_id, entries);
    },
    [activeRow, putRowEntries],
  );

  // ---------------------------------------------------------------------
  // Codebook editing -- still an explicit begin/save/cancel batch, unlike
  // row tagging: renaming/adding/removing several codes at once is a
  // single coherent change a researcher composes, not a one-off action.
  // ---------------------------------------------------------------------

  const beginCodebookEdit = useCallback(() => {
    setCodebookDraft(cloneCodebookTree(codebookTree));
    setCodebookSaveState({ status: "idle", message: "" });
    setIsCodebookEditMode(true);
  }, [codebookTree]);

  const cancelCodebookEdit = useCallback(() => {
    setIsCodebookEditMode(false);
    setCodebookDraft([]);
    setCodebookSaveState({ status: "idle", message: "" });
  }, []);

  const saveCodebookEdit = useCallback(async () => {
    const schema = getSelectedCodingSchema();
    if (!schema) {
      setCodebookSaveState({ status: "error", message: "Unable to resolve coding schema." });
      return;
    }
    setCodebookSaveState({ status: "saving", message: "Saving..." });
    const content = serializeCodebookTreeToText(codebookDraft);
    const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}/codebook`, {
      method: "PUT",
      body: { content: content || " " },
    });
    if (!result.ok) {
      setCodebookSaveState({ status: "error", message: result.error || "Failed to save codebook." });
      return;
    }
    setIsCodebookEditMode(false);
    setCodebookDraft([]);
    setCodebookSaveState({ status: "success", message: "Saved." });
    setRefreshKey((key) => key + 1);
    refreshCurrent();
  }, [codebookDraft, getSelectedCodingSchema, refreshCurrent]);

  // ---------------------------------------------------------------------
  // Rename / duplicate the whole artifact
  // ---------------------------------------------------------------------

  const renameArtifact = useCallback(
    async (displayName) => {
      const schema = getSelectedCodingSchema();
      const trimmed = String(displayName || "").trim();
      if (!schema || !trimmed) return { ok: false, error: "Name is required." };
      const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}`, {
        method: "PATCH",
        body: { display_name: trimmed },
      });
      if (!result.ok) return { ok: false, error: result.error };
      setSelectedCodedDataName(trimmed);
      fetchAvailableCodedData();
      return { ok: true };
    },
    [fetchAvailableCodedData, getSelectedCodingSchema],
  );

  const handleDuplicate = useCallback(
    async (displayName) => {
      const schema = getSelectedCodingSchema();
      if (!schema) return { ok: false, error: "Unable to resolve coding schema." };
      const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}/duplicate`, {
        method: "POST",
        body: { display_name: displayName },
      });
      if (!result.ok) return { ok: false, error: result.error };
      await fetchAvailableCodedData();
      return { ok: true };
    },
    [fetchAvailableCodedData, getSelectedCodingSchema],
  );

  // ---------------------------------------------------------------------
  // Multi-select + AI recode
  // ---------------------------------------------------------------------

  const toggleItemSelected = useCallback((itemId) => {
    if (!itemId) return;
    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => setSelectedItemIds(new Set()), []);

  const [selectAllLoading, setSelectAllLoading] = useState(false);

  // Selects every row matching the current only/code/search filters, not
  // just the current page's 25 -- `rows` only ever holds one page, so
  // this re-fetches with the full matching count as the limit (the same
  // GET /api/coding/{ref}/rows endpoint, reusing whatever filters are
  // already active) rather than being limited to what happens to be
  // loaded client-side.
  const selectAllMatching = useCallback(async () => {
    const schema = getSelectedCodingSchema();
    if (!schema || rowsTotal === 0) return;
    setSelectAllLoading(true);
    const params = new URLSearchParams({ limit: String(rowsTotal), offset: "0", only: onlyFilter || "all" });
    if (searchQuery) params.set("q", searchQuery);
    if (activeFilterCode) params.set("code", activeFilterCode);
    const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}/rows?${params}`, {
      method: "GET",
    });
    setSelectAllLoading(false);
    if (!result.ok) return;
    const matchedIds = (Array.isArray(result.data.rows) ? result.data.rows : []).map((row) => row.item_id);
    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      matchedIds.forEach((id) => next.add(id));
      return next;
    });
  }, [getSelectedCodingSchema, rowsTotal, onlyFilter, searchQuery, activeFilterCode]);

  const recodeThisDocument = useCallback(() => {
    if (!activeItemId) return;
    setSelectedItemIds(new Set([activeItemId]));
  }, [activeItemId]);

  const handleRecodeSelected = useCallback(async () => {
    const schema = getSelectedCodingSchema();
    if (!schema) {
      setRecodeError("Unable to resolve coding schema.");
      return;
    }
    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) {
      setRecodeError("Please set your API key in the navbar first.");
      return;
    }

    let payload;
    try {
      payload = buildRecodeItemsPayload({
        apiKey,
        itemIds: Array.from(selectedItemIds),
        model: recodeModel,
        methodology: recodeMethodology,
      });
    } catch (err) {
      setRecodeError(err instanceof MissingFieldsError ? err.message : String(err));
      return;
    }

    setRecodeLoading(true);
    setRecodeError(null);
    setRecodeProgress(null);
    setRecodeSummary("");

    const result = await postJsonAndPoll(
      `/api/coding/${encodeURIComponent(schema)}/recode`,
      payload,
      { onProgress: setRecodeProgress },
    );

    setRecodeLoading(false);
    if (!result.ok) {
      setRecodeError(result.error || "Recode failed.");
      return;
    }

    const data = result.data || {};
    const rejectedTotal =
      (data.rejected_unknown_item || 0) + (data.rejected_unknown_code || 0) + (data.rejected_quote_not_found || 0);
    if (rejectedTotal > 0) {
      setRecodeSummary(
        `${data.accepted || 0} coding${data.accepted === 1 ? "" : "s"} saved. ` +
          `${rejectedTotal} rejected as unverifiable and were not saved.`,
      );
    }

    clearSelection();
    setRefreshKey((key) => key + 1);
    refreshCurrent();
  }, [
    clearSelection,
    getSelectedCodingSchema,
    recodeMethodology,
    recodeModel,
    refreshCurrent,
    selectedItemIds,
  ]);

  const handleCodedDataChange = useCallback(
    (codedDataId) => {
      setSelectedCodedData(codedDataId);
      const selected = availableCodedData.find((item) => item.id === codedDataId);
      setSelectedCodedDataName(selected?.display_name || selected?.name || codedDataId || "");
    },
    [availableCodedData],
  );

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    fetchAvailableCodedData();
  }, [fetchAvailableCodedData]);

  // Reset all per-artifact state whenever the selected coding file changes.
  useEffect(() => {
    setCodebookTree([]);
    setSystemPrompt("");
    setUserPrompt("");
    setTotalRows(0);
    setTotalCoded(0);
    setRows([]);
    setRowsTotal(0);
    setPage(0);
    setOnlyFilter("all");
    setSearchInput("");
    setSearchQuery("");
    setActiveFilterCode(null);
    setActiveItemId(null);
    setPendingSelection(null);
    setSelectedItemIds(new Set());
    setRowActionError(null);
    setIsCodebookEditMode(false);
    setCodebookDraft([]);
    setCodebookSaveState({ status: "idle", message: "" });
    setRecodeError(null);
    setRecodeProgress(null);
    setRecodeSummary("");
  }, [selectedCodedData]);

  useEffect(() => {
    const schema = getSelectedCodingSchema();
    if (!schema) return;
    fetchCodingArtifact(schema);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCodedData]);

  useEffect(() => {
    const schema = getSelectedCodingSchema();
    if (!schema) return;
    fetchCodingRows(schema, { page, only: onlyFilter, q: searchQuery, code: activeFilterCode });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCodedData, page, onlyFilter, searchQuery, activeFilterCode]);

  // Debounce free-text search before it becomes a server query.
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setPage(0);
      setSearchQuery(searchInput.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timeoutId);
  }, [searchInput]);

  useEffect(() => {
    if (codebookSaveState.status !== "success") return;
    const timeoutId = setTimeout(() => {
      setCodebookSaveState((prev) => (prev.status === "success" ? { status: "idle", message: "" } : prev));
    }, 2400);
    return () => clearTimeout(timeoutId);
  }, [codebookSaveState.status]);

  // Clear a pending text selection whenever the active document changes.
  useEffect(() => {
    setPendingSelection(null);
  }, [activeItemId]);

  const toggleFilterCode = useCallback((code) => {
    setPage(0);
    setActiveFilterCode((prev) => (prev === code ? null : code));
  }, []);

  const pageCount = Math.max(1, Math.ceil(rowsTotal / ROWS_PER_PAGE));
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
    loading: artifactLoading || rowsLoading,
    rows,
    rowsTotal,
    rowsLoading,
    page,
    pageCount,
    onlyFilter,
    setOnlyFilter: (value) => {
      setPage(0);
      setOnlyFilter(value);
    },
    searchInput,
    setSearchInput,
    activeFilterCode,
    toggleFilterCode,
    onPrevPage: () => setPage((p) => Math.max(0, p - 1)),
    onNextPage: () => setPage((p) => Math.min(pageCount - 1, p + 1)),
    codebookTree,
    totalRows,
    totalCoded,
    viewMode,
    setViewMode,
    activeItemId,
    setActiveItemId,
    activeRow,
    pendingSelection,
    handleSelectionChange,
    applyCodeToSelection,
    removeCodeEntry,
    updateEntryNotes,
    rowActionError,
    selectedItemIds,
    toggleItemSelected,
    clearSelection,
    selectAllMatching,
    selectAllLoading,
    recodeThisDocument,
    recodeModel,
    setRecodeModel,
    recodeMethodology,
    setRecodeMethodology,
    recodeLoading,
    recodeProgress,
    recodeError,
    recodeSummary,
    handleRecodeSelected,
    isCodebookEditMode,
    codebookDraft,
    setCodebookDraft,
    codebookSaveState,
    beginCodebookEdit,
    cancelCodebookEdit,
    saveCodebookEdit,
    renameArtifact,
    selectedCodingSchema,
    selectedCodingDescription,
    handleDuplicate,
    handleCodedDataChange,
  };
}
