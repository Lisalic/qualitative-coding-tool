import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch, postJsonAndPoll, requestJson } from "../../../api";
import { buildRecodeItemsPayload, MissingFieldsError } from "../../../lib/apiContracts";
import { cloneCodebookTree, flattenTreeToCodes, groupCodesByFamily } from "../../../lib/codingUtils";
import { normalizeCodingRowEdits } from "../../../lib/codingViewHelpers";

const ROWS_PER_PAGE = 25;
const SEARCH_DEBOUNCE_MS = 400;

/**
 * Backs the 3-pane View Coding workspace (document list / reader pane /
 * codebook sidebar) -- see CodingWorkspaceSection.jsx.
 *
 * Editing is ONE session, not three: manual tagging (select text, click
 * a code / remove a code / edit a note), codebook changes (rename/add/
 * remove a code or family), and accepted AI recode proposals all
 * accumulate as staged, local changes and nothing reaches the server
 * until `saveSession` flushes everything in one
 * `PUT /api/coding/{ref}/revision` call. That call commits at most one
 * new version server-side (see `coding_service.save_coding_revision`),
 * however many of the three kinds of change it contains -- there is no
 * separate save step per concern any more, and no version minted for a
 * mid-session action.
 *
 * State for the two staged pieces:
 * - `pendingRowEdits` (`Map<item_id, entries[]>`): a row's full desired
 *   codes, touched by manual tag/untag/note edits AND by an accepted AI
 *   recode proposal (see `handleRecodeSelected`) -- both replace a row's
 *   codes wholesale, so they share one staging map. `aiProposedItemIds`
 *   tracks which of those came from AI, purely for the "N by AI" badge
 *   in the UI; it does not affect what gets saved.
 * - `codebookDraft`: the codebook tree, edited in place by
 *   `CodeLegend`/`CodingCodebookSidebar` regardless of whether the
 *   sidebar's Edit/Done toggle is currently showing the editor -- the
 *   toggle only switches presentation (see CodingCodebookSidebar.jsx),
 *   it is not a save boundary. `isCodebookDirty` tracks whether the
 *   draft differs from the last-saved `codebookTree`.
 *
 * `discardSession` throws both away and refetches from the server;
 * `saveSession` sends whichever of `codes`/`rows` actually changed.
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
  const [instructions, setInstructions] = useState("");
  const [promptMeta, setPromptMeta] = useState(null);
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

  // Codebook draft is ALWAYS live (not just while the sidebar's edit
  // view is showing) -- see this module's docstring. `isCodebookEditMode`
  // is purely which presentation CodingCodebookSidebar renders.
  const [isCodebookEditMode, setIsCodebookEditMode] = useState(false);
  const [codebookDraft, setCodebookDraft] = useState([]);
  const [isCodebookDirty, setIsCodebookDirty] = useState(false);

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
      setCodebookDraft([]);
      setIsCodebookDirty(false);
      setSystemPrompt("");
      setInstructions("");
      setPromptMeta(null);
      setTotalRows(0);
      setTotalCoded(0);
      return;
    }
    const grouped = groupCodesByFamily(result.data.codes);
    setCodebookTree(grouped);
    // The draft always tracks the server's codebook as its baseline --
    // on first load AND after a successful save (this same function is
    // re-called then, see saveSession) -- so a save leaves nothing
    // "still dirty" behind.
    setCodebookDraft(cloneCodebookTree(grouped));
    setIsCodebookDirty(false);
    setSystemPrompt(result.data.file?.systemprompt || "");
    setInstructions(result.data.file?.instructions || "");
    setPromptMeta(result.data.file?.prompt_meta || null);
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
      const fetchedRows = Array.isArray(result.data.rows) ? result.data.rows : [];
      // Re-apply any not-yet-saved local edits on top of the server's
      // rows -- a page/filter/search change (or an artifact refetch
      // after Save) must not silently drop a pending edit for a row
      // that's still on screen after the refetch.
      const pending = pendingRowEditsRef.current;
      const nextRows =
        pending.size === 0
          ? fetchedRows
          : fetchedRows.map((row) => (pending.has(row.item_id) ? { ...row, codes: pending.get(row.item_id) } : row));
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
  // Row tagging -- staged locally (manual tags AND accepted AI recode
  // proposals alike), not auto-saved per action. Nothing reaches the
  // server until `saveSession` flushes the whole editing session -- see
  // this module's docstring.
  // ---------------------------------------------------------------------

  const [pendingRowEdits, setPendingRowEdits] = useState(() => new Map());
  const pendingRowEditsRef = useRef(pendingRowEdits);
  useEffect(() => {
    pendingRowEditsRef.current = pendingRowEdits;
  }, [pendingRowEdits]);
  const [aiProposedItemIds, setAiProposedItemIds] = useState(() => new Set());
  const [sessionSaveState, setSessionSaveState] = useState({ status: "idle", message: "" });

  const stageRowEdit = useCallback((itemId, entries) => {
    setRows((prev) => prev.map((row) => (row.item_id === itemId ? { ...row, codes: entries } : row)));
    setPendingRowEdits((prev) => {
      const next = new Map(prev);
      next.set(itemId, entries);
      return next;
    });
    setSessionSaveState((prev) => (prev.status === "error" ? { status: "idle", message: "" } : prev));
  }, []);

  const isSessionDirty = pendingRowEdits.size > 0 || isCodebookDirty;
  // Pending rows that came from an accepted AI recode proposal, not a
  // manual edit -- purely for the "N by AI" bit of the bottom bar's
  // summary (see CodingWorkspaceSection.jsx's sessionSummary); it does
  // not affect what gets saved.
  const aiProposedPendingCount = useMemo(() => {
    let count = 0;
    pendingRowEdits.forEach((_, itemId) => {
      if (aiProposedItemIds.has(itemId)) count += 1;
    });
    return count;
  }, [pendingRowEdits, aiProposedItemIds]);

  const saveSession = useCallback(async () => {
    const schema = getSelectedCodingSchema();
    if (!schema || !isSessionDirty) return;

    let normalizedRows = null;
    if (pendingRowEdits.size > 0) {
      const draft = Array.from(pendingRowEdits.entries()).map(([itemId, codes]) => ({ itemId, codes }));
      const normalized = normalizeCodingRowEdits(draft);
      if (!normalized.ok) {
        setSessionSaveState({ status: "error", message: normalized.error });
        return;
      }
      normalizedRows = normalized.rows;
    }

    const body = {};
    if (isCodebookDirty) body.codes = flattenTreeToCodes(codebookDraft);
    if (normalizedRows) body.rows = normalizedRows;
    // Recode's model is provenance for the version, not something the
    // save itself needs to succeed -- only attach it when this save
    // actually includes an accepted AI proposal.
    if (aiProposedItemIds.size > 0 && recodeModel) body.model = recodeModel;

    setSessionSaveState({ status: "saving", message: "Saving..." });
    const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}/revision`, {
      method: "PUT",
      body,
    });
    if (!result.ok) {
      setSessionSaveState({ status: "error", message: result.error || "Failed to save." });
      return;
    }
    setPendingRowEdits(new Map());
    setAiProposedItemIds(new Set());
    setSessionSaveState({ status: "success", message: "Saved." });
    setRefreshKey((key) => key + 1);
    // Also resets codebookDraft/isCodebookDirty from the freshly saved
    // tree -- see fetchCodingArtifact.
    fetchCodingArtifact(schema);
  }, [
    aiProposedItemIds,
    codebookDraft,
    fetchCodingArtifact,
    getSelectedCodingSchema,
    isCodebookDirty,
    isSessionDirty,
    pendingRowEdits,
    recodeModel,
  ]);

  const discardSession = useCallback(() => {
    setPendingRowEdits(new Map());
    setAiProposedItemIds(new Set());
    setCodebookDraft(cloneCodebookTree(codebookTree));
    setIsCodebookDirty(false);
    setIsCodebookEditMode(false);
    setSessionSaveState({ status: "idle", message: "" });
    refreshCurrent();
  }, [codebookTree, refreshCurrent]);

  const activeRow = useMemo(
    () => rows.find((row) => row.item_id === activeItemId) || null,
    [rows, activeItemId],
  );

  // Stable identity (no deps) so the effect in HighlightedContent that
  // reports selection changes up to here doesn't see a new function on
  // every render -- an unstable callback there previously created a
  // feedback loop: new callback -> effect re-fires -> setPendingSelection
  // with a new object -> re-render -> new callback -> ... forever.
  // `selection` is `{ text, start, end, left, top }` (offsets computed
  // directly from the real DOM range in HighlightedContent, `left`/`top`
  // its on-screen anchor -- see its module comment) or `null` when
  // explicitly cleared. Once captured, a selection is STICKY: this does
  // NOT clear just because the underlying browser selection collapsed --
  // see HighlightedContent's own comment for why that used to make the
  // popup flash shut the instant it opened.
  const handleSelectionChange = useCallback((selection) => {
    setPendingSelection((prev) => {
      if (!selection) return prev === null ? prev : null;
      if (
        prev &&
        prev.text === selection.text &&
        prev.start === selection.start &&
        prev.end === selection.end &&
        prev.left === selection.left &&
        prev.top === selection.top
      ) {
        return prev;
      }
      return selection;
    });
  }, []);

  const applyCodeToSelection = useCallback(
    (codeUid) => {
      if (!activeRow || !pendingSelection?.text || !codeUid) return;
      const entries = [
        ...(Array.isArray(activeRow.codes) ? activeRow.codes : []),
        {
          code_uid: codeUid,
          quote: pendingSelection.text,
          start_offset: pendingSelection.start,
          end_offset: pendingSelection.end,
          notes: null,
        },
      ];
      stageRowEdit(activeRow.item_id, entries);
      setPendingSelection(null);
    },
    [activeRow, pendingSelection, stageRowEdit],
  );

  const removeCodeEntry = useCallback(
    (entryIndex) => {
      if (!activeRow) return;
      const entries = (Array.isArray(activeRow.codes) ? activeRow.codes : []).filter(
        (_, idx) => idx !== entryIndex,
      );
      stageRowEdit(activeRow.item_id, entries);
    },
    [activeRow, stageRowEdit],
  );

  const updateEntryNotes = useCallback(
    (entryIndex, notes) => {
      if (!activeRow) return;
      const entries = (Array.isArray(activeRow.codes) ? activeRow.codes : []).map((entry, idx) =>
        idx === entryIndex ? { ...entry, notes } : entry,
      );
      stageRowEdit(activeRow.item_id, entries);
    },
    [activeRow, stageRowEdit],
  );

  // ---------------------------------------------------------------------
  // Codebook editing -- the draft is always live (see this module's
  // docstring); `isCodebookEditMode` only switches which presentation
  // CodingCodebookSidebar renders. Cancel reverts the draft to the
  // last-saved codebookTree (discarding any codebook edits made this
  // session) and drops back to the read-only view; Done just drops back
  // to the read-only view, keeping whatever's in the draft for the next
  // Save Changes.
  // ---------------------------------------------------------------------

  const handleCodebookDraftChange = useCallback((nextTree) => {
    setCodebookDraft(nextTree);
    setIsCodebookDirty(true);
  }, []);

  const beginCodebookEdit = useCallback(() => {
    setIsCodebookEditMode(true);
  }, []);

  const finishCodebookEdit = useCallback(() => {
    setIsCodebookEditMode(false);
  }, []);

  const cancelCodebookEdit = useCallback(() => {
    setCodebookDraft(cloneCodebookTree(codebookTree));
    setIsCodebookDirty(false);
    setIsCodebookEditMode(false);
  }, [codebookTree]);

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
    async (displayName, fromVersionNo) => {
      const schema = getSelectedCodingSchema();
      if (!schema) return { ok: false, error: "Unable to resolve coding schema." };
      const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}/duplicate`, {
        method: "POST",
        body: { display_name: displayName, from_version_no: fromVersionNo || undefined },
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
        `${data.accepted || 0} coding${data.accepted === 1 ? "" : "s"} proposed. ` +
          `${rejectedTotal} rejected as unverifiable and were not proposed.`,
      );
    }

    // A recode is a proposal, not a write (see coding_service's
    // _run_recode_items_job) -- stage each returned row into the same
    // pending-edits map manual tags use, overwriting whatever was
    // pending for that row (full-row replacement, same as the
    // server-side semantics). Nothing is committed until Save Changes.
    const proposals = Array.isArray(data.proposals) ? data.proposals : [];
    setPendingRowEdits((prev) => {
      const next = new Map(prev);
      proposals.forEach((proposal) => next.set(proposal.item_id, proposal.codes || []));
      return next;
    });
    setRows((prev) =>
      prev.map((row) => {
        const proposal = proposals.find((p) => p.item_id === row.item_id);
        return proposal ? { ...row, codes: proposal.codes || [] } : row;
      }),
    );
    setAiProposedItemIds((prev) => {
      const next = new Set(prev);
      proposals.forEach((proposal) => next.add(proposal.item_id));
      return next;
    });

    clearSelection();
  }, [
    clearSelection,
    getSelectedCodingSchema,
    recodeMethodology,
    recodeModel,
    selectedItemIds,
  ]);

  const handleCodedDataChange = useCallback(
    (codedDataId) => {
      if (isSessionDirty && !window.confirm("You have unsaved coding changes. Switch files and discard them?")) {
        return;
      }
      setSelectedCodedData(codedDataId);
      const selected = availableCodedData.find((item) => item.id === codedDataId);
      setSelectedCodedDataName(selected?.display_name || selected?.name || codedDataId || "");
    },
    [availableCodedData, isSessionDirty],
  );

  // Warn on tab close/reload while the editing session hasn't been saved.
  useEffect(() => {
    if (!isSessionDirty) return undefined;
    const handler = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isSessionDirty]);

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
    setInstructions("");
    setPromptMeta(null);
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
    setPendingRowEdits(new Map());
    setAiProposedItemIds(new Set());
    setSessionSaveState({ status: "idle", message: "" });
    setIsCodebookEditMode(false);
    setCodebookDraft([]);
    setIsCodebookDirty(false);
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
    if (sessionSaveState.status !== "success") return;
    const timeoutId = setTimeout(() => {
      setSessionSaveState((prev) => (prev.status === "success" ? { status: "idle", message: "" } : prev));
    }, 2400);
    return () => clearTimeout(timeoutId);
  }, [sessionSaveState.status]);

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
    instructions,
    promptMeta,
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
    aiProposedItemIds,
    aiProposedPendingCount,
    pendingRowEditCount: pendingRowEdits.size,
    isCodebookDirty,
    isSessionDirty,
    sessionSaveState,
    saveSession,
    discardSession,
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
    setCodebookDraft: handleCodebookDraftChange,
    beginCodebookEdit,
    finishCodebookEdit,
    cancelCodebookEdit,
    renameArtifact,
    selectedCodingSchema,
    selectedCodingDescription,
    handleDuplicate,
    handleCodedDataChange,
  };
}
