import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch, postJsonAndPoll, requestJson } from "../../../api";
import { buildRecodeItemsPayload, MissingFieldsError } from "../../../lib/apiContracts";
import { cloneCodebookTree, flattenTreeToCodes, groupCodesByFamily, rollUpCoder } from "../../../lib/codingUtils";
import { normalizeCodingRowEdits } from "../../../lib/codingViewHelpers";

const ROWS_PER_PAGE = 25;
const SEARCH_DEBOUNCE_MS = 400;

/**
 * Backs the 3-pane View Coding workspace (document list / reader pane /
 * codebook sidebar) -- see CodingWorkspaceSection.jsx.
 *
 * Editing is ONE session, not three: manual tagging, codebook changes
 * (rename/add/remove a code or family), and accepted AI recode proposals
 * all accumulate as staged, local changes and nothing reaches the server
 * until `saveSession` flushes everything in one
 * `PUT /api/coding/{ref}/revision` call -- at most one new version
 * server-side however many of the three kinds of change it contains.
 *
 * The two staged pieces: `pendingRowEdits` (`Map<item_id, entries[]>`) is
 * a row's full desired codes, touched by manual edits and by an accepted
 * recode proposal alike, since both replace a row's codes wholesale.
 * Each entry carries its own `coder`/`assist_job_id` for attribution.
 * `codebookDraft` is the codebook tree, edited in place regardless of
 * whether the sidebar's Edit/Done toggle is showing the editor -- that
 * toggle only switches presentation, it is not a save boundary;
 * `isCodebookDirty` tracks whether it differs from the last-saved tree.
 * `discardSession` throws both away and refetches; `saveSession` sends
 * whichever of `codes`/`rows` actually changed.
 *
 * Two surfaces drive this one hook via its `pinned` mode: View Coding
 * passes nothing and lets the user pick a file; Apply Codebook passes
 * `pinned` plus the artifact it just created, skipping the picker
 * entirely. `pinned` is its own flag rather than inferred from
 * `pinnedRef` because Apply Codebook's setup step has no artifact yet --
 * a null ref there means "not created", not "fall back to the picker".
 * Everything past that point is identical, which is why the two pages
 * share a workspace instead of growing two of them.
 */
export default function useViewCodingPage({
  pinned = false,
  pinnedRef = null,
  pinnedName = "",
  pinnedDescription = "",
} = {}) {
  const location = useLocation();
  const isPinned = pinned;
  const [availableCodedData, setAvailableCodedData] = useState([]);
  const [pickedCodedData, setSelectedCodedData] = useState(null);
  const [pickedCodedDataName, setSelectedCodedDataName] = useState("");
  // Pinned mode reads straight through to the props rather than mirroring
  // them into state via an effect: an effect lands a render late, so the
  // first frame after Apply Codebook creates an artifact would render the
  // "select a coding" empty state before correcting itself.
  // A rename inside a pinned workspace has nowhere to write back to (the
  // owner supplied the name as a prop), so it is held here until the
  // pinned artifact itself changes.
  const [renamedName, setRenamedName] = useState(null);
  const selectedCodedData = isPinned ? pinnedRef : pickedCodedData;
  const selectedCodedDataName = isPinned ? renamedName ?? pinnedName : pickedCodedDataName;
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
  // C2 assist provenance for this session's recode runs, one entry per
  // `POST /api/coding/{ref}/recode` call: `{jobId, proposedItemIds}`,
  // where `proposedItemIds` is EVERY item the model returned a proposal
  // for, even one skipped for being already hand-edited (see
  // `handleRecodeSelected`) -- a skipped item is exactly "proposed but
  // not accepted", i.e. dismissed. `buildRecodeAssistRuns` (below) turns
  // this into the `assist_runs` the save sends, evaluated against the
  // FINAL staged state rather than at proposal time, so a row accepted
  // now and hand-edited later correctly counts as dismissed too.
  const [recodeRuns, setRecodeRuns] = useState([]);
  // Rows the researcher tagged BY HAND this session. Written only by
  // `stageRowEdit` (manual tag/untag/note), never by an accepted
  // proposal, so it is exactly the set a recode must not overwrite --
  // see `handleRecodeSelected`.
  const humanEditedItemIds = useRef(new Set());
  const [sessionSaveState, setSessionSaveState] = useState({ status: "idle", message: "" });

  const stageRowEdit = useCallback((itemId, entries) => {
    humanEditedItemIds.current.add(itemId);
    setRows((prev) => prev.map((row) => (row.item_id === itemId ? { ...row, codes: entries } : row)));
    setPendingRowEdits((prev) => {
      const next = new Map(prev);
      next.set(itemId, entries);
      return next;
    });
    setSessionSaveState((prev) => (prev.status === "error" ? { status: "idle", message: "" } : prev));
  }, []);

  const isSessionDirty = pendingRowEdits.size > 0 || isCodebookDirty;
  // Pending rows an AI recode contributed to, in their FINAL staged form
  // -- derived from the row's own entries (rollUpCoder), not a
  // session-long "was ever proposed" flag, so a row later hand-edited on
  // top of an accepted proposal correctly stops counting as AI-only.
  // Purely for the "N by AI" bit of the bottom bar's summary (see
  // CodingWorkspaceSection.jsx's sessionSummary); it does not affect
  // what gets saved.
  const aiProposedPendingCount = useMemo(() => {
    let count = 0;
    pendingRowEdits.forEach((entries) => {
      const mark = rollUpCoder(entries);
      if (mark === "ai" || mark === "both") count += 1;
    });
    return count;
  }, [pendingRowEdits]);

  /** Reduce `recodeRuns` against the CURRENT `pendingRowEdits`/`rows`
   * into `assist_runs` for the save -- an item counts as accepted only
   * if its final entries are non-empty and EVERY one is still
   * `coder: "ai"` from THIS run's job, unmodified since. */
  const buildRecodeAssistRuns = useCallback(() => {
    if (recodeRuns.length === 0) return [];
    const finalEntriesFor = (itemId) => {
      if (pendingRowEdits.has(itemId)) return pendingRowEdits.get(itemId) || [];
      return rows.find((r) => r.item_id === itemId)?.codes || [];
    };
    return recodeRuns.map((run) => {
      const acceptedRefs = run.proposedItemIds.filter((itemId) => {
        const entries = finalEntriesFor(itemId);
        return entries.length > 0 && entries.every((e) => e.coder === "ai" && e.assist_job_id === run.jobId);
      });
      return {
        job_id: run.jobId,
        proposed_count: run.proposedItemIds.length,
        accepted_count: acceptedRefs.length,
        dismissed_count: run.proposedItemIds.length - acceptedRefs.length,
        accepted_refs: acceptedRefs,
      };
    });
  }, [recodeRuns, pendingRowEdits, rows]);

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
    const assistRuns = buildRecodeAssistRuns();
    if (assistRuns.length > 0) body.assist_runs = assistRuns;

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
    setRecodeRuns([]);
    humanEditedItemIds.current = new Set();
    setSessionSaveState({ status: "success", message: "Saved." });
    setRefreshKey((key) => key + 1);
    // Also resets codebookDraft/isCodebookDirty from the freshly saved
    // tree -- see fetchCodingArtifact.
    fetchCodingArtifact(schema);
  }, [
    buildRecodeAssistRuns,
    codebookDraft,
    fetchCodingArtifact,
    getSelectedCodingSchema,
    isCodebookDirty,
    isSessionDirty,
    pendingRowEdits,
  ]);

  const discardSession = useCallback(() => {
    setPendingRowEdits(new Map());
    setRecodeRuns([]);
    humanEditedItemIds.current = new Set();
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
          // B1 attribution -- a quote picked by hand here is never an AI
          // recode proposal. Existing entries in the spread above (human
          // or AI) keep whatever coder they already had.
          coder: "human",
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
      setRenamedName(trimmed);
      if (!isPinned) fetchAvailableCodedData();
      return { ok: true };
    },
    [fetchAvailableCodedData, getSelectedCodingSchema, isPinned],
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
      if (!isPinned) await fetchAvailableCodedData();
      return { ok: true };
    },
    [fetchAvailableCodedData, getSelectedCodingSchema, isPinned],
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

  // Selects every row matching the current code/search filters, not just
  // the current page's 25 -- `rows` only ever holds one page, so this
  // re-fetches with the full matching count as the limit (the same
  // GET /api/coding/{ref}/rows endpoint, reusing whatever filters are
  // already active) rather than being limited to what happens to be
  // loaded client-side.
  //
  // `only` is a parameter rather than always `onlyFilter` so the caller
  // can ask for the uncoded rows specifically without first changing the
  // list's filter and changing it back.
  const selectMatching = useCallback(
    async (only) => {
      const schema = getSelectedCodingSchema();
      if (!schema || rowsTotal === 0) return;
      setSelectAllLoading(true);
      const params = new URLSearchParams({ limit: String(rowsTotal), offset: "0", only });
      if (searchQuery) params.set("q", searchQuery);
      if (activeFilterCode) params.set("code", activeFilterCode);
      const result = await requestJson(`/api/coding/${encodeURIComponent(schema)}/rows?${params}`, {
        method: "GET",
      });
      setSelectAllLoading(false);
      if (!result.ok) return;
      const matchedIds = (Array.isArray(result.data.rows) ? result.data.rows : []).map(
        (row) => row.item_id,
      );
      setSelectedItemIds((prev) => {
        const next = new Set(prev);
        matchedIds.forEach((id) => next.add(id));
        return next;
      });
    },
    [getSelectedCodingSchema, rowsTotal, searchQuery, activeFilterCode],
  );

  const selectAllMatching = useCallback(
    () => selectMatching(onlyFilter || "all"),
    [selectMatching, onlyFilter],
  );

  /**
   * Select only the rows nothing has coded yet.
   *
   * The counterpart of the filter editor sending its decided ids so the
   * AI never re-litigates them: it keeps a recode aimed at the rows still
   * awaiting a decision, instead of asking the model to redo work the
   * researcher has already reviewed (and, before the `humanEditedItemIds`
   * guard in `handleRecodeSelected`, silently overwrite it).
   */
  const selectUncodedMatching = useCallback(() => selectMatching("uncoded"), [selectMatching]);

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
    // pending-edits map manual tags use (full-row replacement, matching
    // the server-side semantics). Nothing is committed until Save
    // Changes.
    //
    // A row the researcher already coded BY HAND this session is left
    // alone, even when it was in the selection sent for recoding. The
    // assistant may add, never overwrite -- the same rule
    // `filterEditorState.applyAiResult` enforces by refusing to touch a
    // row the user already ruled on. Without this, selecting "all
    // matching" and recoding silently discarded the tags the researcher
    // had just placed, with no way to get them back short of discarding
    // the whole session.
    const jobId = result.jobId;
    const allProposals = Array.isArray(data.proposals) ? data.proposals : [];
    const proposals = allProposals.filter(
      (proposal) => !humanEditedItemIds.current.has(proposal.item_id),
    );
    const skipped = allProposals.length - proposals.length;
    if (skipped > 0) {
      setRecodeSummary((prev) =>
        [
          prev,
          `${proposals.length} row${proposals.length === 1 ? "" : "s"} updated by AI. ` +
            `${skipped} left as you coded ${skipped === 1 ? "it" : "them"} by hand.`,
        ]
          .filter(Boolean)
          .join(" "),
      );
    }

    // B1 attribution: every entry a recode proposal carries is stamped
    // `coder: "ai"` plus this run's `job_id` -- what
    // `assist_service.resolve_ai_coder_model` validates on save, and what
    // `buildRecodeAssistRuns` (above) reads back to compute accepted/
    // dismissed counts.
    const taggedCodesByItem = new Map(
      proposals.map((proposal) => [
        proposal.item_id,
        (proposal.codes || []).map((entry) => ({ ...entry, coder: "ai", assist_job_id: jobId })),
      ]),
    );

    setPendingRowEdits((prev) => {
      const next = new Map(prev);
      taggedCodesByItem.forEach((codes, itemId) => next.set(itemId, codes));
      return next;
    });
    setRows((prev) =>
      prev.map((row) =>
        taggedCodesByItem.has(row.item_id) ? { ...row, codes: taggedCodesByItem.get(row.item_id) } : row,
      ),
    );
    // Every item the model proposed for, INCLUDING one skipped above for
    // already being hand-edited -- a skip is "proposed but not accepted",
    // which `buildRecodeAssistRuns` needs to count it as dismissed rather
    // than silently dropping it from the provenance record.
    if (jobId && allProposals.length > 0) {
      setRecodeRuns((prev) => [...prev, { jobId, proposedItemIds: allProposals.map((p) => p.item_id) }]);
    }

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

  // Both lists exist only to feed the picker, so a pinned workspace skips
  // them -- Apply Codebook already knows which artifact it is showing.
  useEffect(() => {
    if (isPinned) return;
    fetchProjects();
  }, [isPinned, fetchProjects]);

  useEffect(() => {
    if (isPinned) return;
    fetchAvailableCodedData();
  }, [isPinned, fetchAvailableCodedData]);

  // Reset all per-artifact state whenever the selected coding file changes.
  useEffect(() => {
    setRenamedName(null);
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
    setRecodeRuns([]);
    humanEditedItemIds.current = new Set();
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
  const selectedCodingDescription = isPinned
    ? pinnedDescription
    : availableCodedData.find((codedData) => codedData.id === selectedCodedData)?.description;

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
    selectUncodedMatching,
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
