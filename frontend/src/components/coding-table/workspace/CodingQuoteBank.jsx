import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch, requestJson } from "../../../api";
import {
  btn,
  btnSm,
  btnActive,
  btnPrimary,
  inputSm,
  select,
  badge,
  meta,
} from "../../../lib/uiClasses";
import { getCodeColor } from "../../../lib/codingUtils";
import { formatCitation, DEFAULT_CITATION_OPTIONS } from "../../../lib/citationHelpers";
import PageEmptyState from "../../primitives/PageEmptyState";

const PAGE_SIZE = 25;

export default function CodingQuoteBank({ schema, availableCodes = [], refreshKey = 0 }) {
  const [quotes, setQuotes] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [codeFilter, setCodeFilter] = useState("");
  const [coderFilter, setCoderFilter] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [starredOnly, setStarredOnly] = useState(false);
  const [page, setPage] = useState(0);

  // Active selection & UI overlays
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [inspectQuote, setInspectQuote] = useState(null);
  const [citationModalQuote, setCitationModalQuote] = useState(null);
  const [citationOptions, setCitationOptions] = useState(DEFAULT_CITATION_OPTIONS);
  const [copiedNotification, setCopiedNotification] = useState(false);

  // Note editing state: entry_id -> string draft
  const [editingNoteId, setEditingNoteId] = useState(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);

  // A failed star/note write, shown in the toolbar until the next action.
  const [actionError, setActionError] = useState(null);

  const rowRefs = useRef([]);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearchQuery(searchInput.trim());
      setPage(0);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Reset page when filters change
  const handleCodeFilterChange = (e) => {
    setCodeFilter(e.target.value);
    setPage(0);
  };

  const handleCoderFilterChange = (e) => {
    setCoderFilter(e.target.value);
    setPage(0);
  };

  const handleStarredToggle = () => {
    setStarredOnly((prev) => !prev);
    setPage(0);
  };

  // Fetch quotes
  const fetchQuotes = useCallback(async () => {
    if (!schema) return;
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(page * PAGE_SIZE));
    if (codeFilter) params.set("code", codeFilter);
    if (coderFilter !== "all") params.set("coder", coderFilter);
    if (searchQuery) params.set("q", searchQuery);
    if (starredOnly) params.set("starred_only", "true");

    try {
      const res = await apiFetch(`/api/coding/${encodeURIComponent(schema)}/quotes?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setQuotes(data.quotes || []);
      setTotal(data.total || 0);
      setSelectedIndex(0);
    } catch (err) {
      setError(err?.message || "Failed to load quotes");
    } finally {
      setLoading(false);
    }
  }, [schema, codeFilter, coderFilter, searchQuery, starredOnly, page]);

  useEffect(() => {
    fetchQuotes();
  }, [fetchQuotes, refreshKey]);

  // Apply a patch to one quote everywhere it's shown: the list and, if
  // it's the one open, the Inspect dialog's snapshot.
  const patchQuote = useCallback((id, patch) => {
    setQuotes((prev) => prev.map((q) => (q.id === id ? { ...q, ...patch } : q)));
    setInspectQuote((prev) => (prev?.id === id ? { ...prev, ...patch } : prev));
  }, []);

  // Star / Unstar
  const handleToggleStar = useCallback(async (quote) => {
    const nextStarred = !quote.starred;
    setActionError(null);
    patchQuote(quote.id, { starred: nextStarred });
    try {
      const res = await requestJson(
        `/api/coding/${encodeURIComponent(schema)}/quotes/${quote.id}/star`,
        { method: "PUT", body: { starred: nextStarred } },
      );
      if (!res.ok) throw new Error(res.error || "Failed to update star");
      // Under "Starred only", an unstarred quote no longer belongs in the list.
      if (starredOnly && !nextStarred) {
        setQuotes((prev) => prev.filter((q) => q.id !== quote.id));
        setTotal((prev) => Math.max(0, prev - 1));
      }
    } catch (err) {
      patchQuote(quote.id, { starred: quote.starred });
      setActionError(err?.message || "Failed to update star");
    }
  }, [schema, starredOnly, patchQuote]);

  // Start Note Editing
  const startEditingNote = (quote) => {
    setEditingNoteId(quote.id);
    setNoteDraft(quote.notes || "");
  };

  const cancelEditingNote = () => {
    setEditingNoteId(null);
    setNoteDraft("");
  };

  // A note edit is saved as a new coding version, so the quote comes
  // back under a new entry id -- adopt it so later stars/edits target
  // the live entry.
  const saveNote = async (quote) => {
    setNoteSaving(true);
    setActionError(null);
    const updatedNotes = noteDraft.trim() || null;
    try {
      const res = await requestJson(
        `/api/coding/${encodeURIComponent(schema)}/quotes/${quote.id}/notes`,
        { method: "PATCH", body: { notes: updatedNotes } },
      );
      if (!res.ok) throw new Error(res.error || "Failed to save note");
      patchQuote(quote.id, {
        id: res.data?.entry_id ?? quote.id,
        notes: res.data?.notes ?? updatedNotes,
      });
      setEditingNoteId(null);
    } catch (err) {
      setActionError(err?.message || "Failed to save note");
    } finally {
      setNoteSaving(false);
    }
  };

  // Quick Copy Citation
  const copyCitationToClipboard = async (quote, customOpts = null) => {
    const text = formatCitation(quote, customOpts || citationOptions);
    try {
      await navigator.clipboard.writeText(text);
      setCopiedNotification(true);
      setTimeout(() => setCopiedNotification(false), 2000);
    } catch (err) {
      console.error("Failed to copy citation:", err);
    }
  };

  // Keep keyboard focus on the selected row as j/k moves it.
  const focusSelectedRow = useRef(false);
  useEffect(() => {
    if (!focusSelectedRow.current) return;
    focusSelectedRow.current = false;
    rowRefs.current[selectedIndex]?.focus();
  }, [selectedIndex]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Do nothing if typing inside input, textarea, or select
      const tag = e.target?.tagName ? e.target.tagName.toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || tag === "select") {
        if (e.key === "Escape" && editingNoteId != null) {
          cancelEditingNote();
        }
        return;
      }
      // A focused button/link keeps its native Enter/Space activation, and
      // the single-letter shortcuts don't fire from it either.
      if (e.target?.closest?.("button, a, [contenteditable='true']")) return;

      if (inspectQuote || citationModalQuote) {
        if (e.key === "Escape") {
          setInspectQuote(null);
          setCitationModalQuote(null);
        }
        return;
      }

      if (quotes.length === 0) return;

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        focusSelectedRow.current = true;
        setSelectedIndex((prev) => Math.min(quotes.length - 1, prev + 1));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        focusSelectedRow.current = true;
        setSelectedIndex((prev) => Math.max(0, prev - 1));
      } else if (e.key === "s") {
        e.preventDefault();
        const currentQuote = quotes[selectedIndex];
        if (currentQuote) handleToggleStar(currentQuote);
      } else if (e.key === "c") {
        e.preventDefault();
        const currentQuote = quotes[selectedIndex];
        if (currentQuote) setCitationModalQuote(currentQuote);
      } else if (e.key === "e") {
        e.preventDefault();
        const currentQuote = quotes[selectedIndex];
        if (currentQuote) startEditingNote(currentQuote);
      } else if (e.key === "Enter" || e.key === "o") {
        e.preventDefault();
        const currentQuote = quotes[selectedIndex];
        if (currentQuote) setInspectQuote(currentQuote);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [quotes, selectedIndex, inspectQuote, citationModalQuote, editingNoteId, handleToggleStar]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex h-full flex-col overflow-hidden bg-ink text-paper">
      {/* Toast notification */}
      {copiedNotification && (
        <div
          role="status"
          aria-live="polite"
          className="fixed top-4 right-4 z-50 border border-success bg-ink px-3 py-1.5 text-xs font-semibold text-success shadow-md"
        >
          ✓ Citation copied to clipboard
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface p-3 shrink-0">
        <div className="flex flex-wrap items-center gap-2">
          {/* Search */}
          <input
            type="search"
            aria-label="Search quotes"
            placeholder="Search quotes, notes, context..."
            className={`${inputSm} w-52 sm:w-64`}
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />

          {/* Code Filter */}
          <select
            aria-label="Filter by code"
            className={select}
            value={codeFilter}
            onChange={handleCodeFilterChange}
          >
            <option value="">All Codes</option>
            {availableCodes.map((c) => (
              <option key={c.code_uid || c.name} value={c.code_uid || c.name}>
                {c.name}
              </option>
            ))}
          </select>

          {/* Coder Filter */}
          <select
            aria-label="Filter by coder"
            className={select}
            value={coderFilter}
            onChange={handleCoderFilterChange}
          >
            <option value="all">All Coders</option>
            <option value="human">Human</option>
            <option value="ai">AI</option>
          </select>

          {/* Starred Only Toggle */}
          <button
            type="button"
            className={`${btnSm} ${starredOnly ? btnActive : ""}`}
            onClick={handleStarredToggle}
            title="Filter by starred quotes"
          >
            ★ Starred only
          </button>
        </div>

        {/* Status and count */}
        <div className="flex items-center gap-3">
          {actionError && (
            <span role="alert" className="text-xs text-error">
              {actionError}
            </span>
          )}
          <span className={meta}>
            {total === 0
              ? "0 quotes"
              : `Showing ${page * PAGE_SIZE + 1}–${Math.min(total, (page + 1) * PAGE_SIZE)} of ${total}`}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              className={btnSm}
              disabled={page === 0 || loading}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              aria-label="Previous page"
            >
              Prev
            </button>
            <span className="px-1 text-xs text-paper/70">
              {page + 1} / {totalPages}
            </span>
            <button
              type="button"
              className={btnSm}
              disabled={page >= totalPages - 1 || loading}
              onClick={() => setPage((p) => p + 1)}
              aria-label="Next page"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Main Quote List Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {loading && quotes.length === 0 ? (
          <div className="p-8 text-center text-sm text-paper/60">Loading quotes...</div>
        ) : error ? (
          <div className="border border-error bg-error/10 p-4 text-sm text-error">{error}</div>
        ) : quotes.length === 0 ? (
          <PageEmptyState
            title="No quotes found"
            message={
              starredOnly
                ? "No starred quotes yet."
                : "No coded quotes match the current filters."
            }
          />
        ) : (
          quotes.map((q, idx) => {
            const isSelected = idx === selectedIndex;
            const isEditingNote = editingNoteId === q.id;
            const codeColor = getCodeColor(q.code_uid);

            return (
              <div
                key={q.id}
                ref={(el) => (rowRefs.current[idx] = el)}
                tabIndex={0}
                onFocus={() => setSelectedIndex(idx)}
                onClick={() => setSelectedIndex(idx)}
                className={`border p-4 transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-paper ${
                  isSelected
                    ? "border-paper bg-surface-raised"
                    : "border-line bg-surface hover:border-line-soft"
                }`}
              >
                {/* Header row: Star, Code, Coder, Item ID, Actions */}
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft pb-2.5">
                  <div className="flex items-center gap-2">
                    {/* Star Button */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleStar(q);
                      }}
                      className={`text-base leading-none transition-colors hover:scale-110 ${
                        q.starred ? "text-paper" : "text-paper/30 hover:text-paper"
                      }`}
                      title={q.starred ? "Starred for evidence (s)" : "Star quote (s)"}
                      aria-label={q.starred ? "Unstar quote" : "Star quote"}
                    >
                      {q.starred ? "★" : "☆"}
                    </button>

                    {/* Code Badge */}
                    <span
                      className="border px-2 py-0.5 text-xs font-semibold"
                      style={{
                        borderColor: codeColor || "currentColor",
                        color: codeColor || "inherit",
                      }}
                    >
                      {q.code}
                    </span>

                    {/* Coder Badge */}
                    <span className={badge}>
                      {q.coder === "ai"
                        ? `AI${q.coder_model ? `: ${q.coder_model}` : ""}`
                        : "HUMAN"}
                    </span>

                    {/* Target identifier & offsets */}
                    <span className={meta}>
                      {q.row_type} #{q.post_id}
                      {q.start_offset != null && q.end_offset != null && (
                        <> · [{q.start_offset}:{q.end_offset}]</>
                      )}
                    </span>
                  </div>

                  {/* Actions right */}
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      className={btnSm}
                      onClick={(e) => {
                        e.stopPropagation();
                        setCitationModalQuote(q);
                      }}
                      title="Copy citation with attribution options (c)"
                    >
                      Citation
                    </button>
                    <button
                      type="button"
                      className={btnSm}
                      onClick={(e) => {
                        e.stopPropagation();
                        setInspectQuote(q);
                      }}
                      title="Inspect quote in full source context (Enter / o)"
                    >
                      Inspect Source
                    </button>
                  </div>
                </div>

                {/* Quote Text */}
                <div className="my-3 pl-3 border-l-2 border-paper/40">
                  <blockquote className="text-sm italic text-paper/90 leading-relaxed select-text">
                    &ldquo;{q.quote}&rdquo;
                  </blockquote>
                </div>

                {/* Document context title snippet */}
                {q.title && (
                  <div className="mb-2 text-xs text-paper/60 truncate">
                    From: <span className="font-medium text-paper/80">{q.title}</span>
                  </div>
                )}

                {/* Notes section */}
                <div className="mt-2 text-xs border-t border-line-soft pt-2">
                  {isEditingNote ? (
                    <div className="space-y-2">
                      <textarea
                        value={noteDraft}
                        onChange={(e) => setNoteDraft(e.target.value)}
                        placeholder="Attach note for writing draft..."
                        rows={2}
                        className="w-full border border-paper bg-surface-raised p-2 text-xs text-paper focus:outline-none focus:ring-1 focus:ring-paper"
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <button
                          type="button"
                          className={`${btnSm} ${btnActive}`}
                          disabled={noteSaving}
                          onClick={() => saveNote(q)}
                        >
                          {noteSaving ? "Saving..." : "Save Note"}
                        </button>
                        <button
                          type="button"
                          className={btnSm}
                          disabled={noteSaving}
                          onClick={cancelEditingNote}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-start justify-between gap-2">
                      {q.notes ? (
                        <div className="flex-1 text-paper/80 bg-white/5 p-2 border border-line-soft">
                          <span className="font-semibold text-paper/60 uppercase text-[10px] block mb-0.5">
                            Note:
                          </span>
                          {q.notes}
                        </div>
                      ) : (
                        <span className="text-paper/40 italic">No notes attached</span>
                      )}
                      <button
                        type="button"
                        className={btnSm}
                        onClick={() => startEditingNote(q)}
                        title="Edit note (e)"
                      >
                        {q.notes ? "Edit Note" : "+ Add Note"}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Source Context Inspection Drawer / Modal */}
      {inspectQuote && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="inspect-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4"
          onClick={() => setInspectQuote(null)}
        >
          <div
            className="flex max-h-[85vh] w-full max-w-3xl flex-col border border-paper bg-ink shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-line p-3">
              <div>
                <h3 id="inspect-dialog-title" className="text-sm font-semibold">
                  Source Context Inspection
                </h3>
                <div className={meta}>
                  {inspectQuote.row_type} #{inspectQuote.post_id} · Offsets: [
                  {inspectQuote.start_offset}:{inspectQuote.end_offset}]
                </div>
              </div>
              <button
                type="button"
                className={btnSm}
                onClick={() => setInspectQuote(null)}
                aria-label="Close dialog"
              >
                ✕ Close
              </button>
            </div>

            {/* Content info */}
            <div className="border-b border-line-soft bg-surface p-3 text-xs space-y-1">
              {inspectQuote.title && (
                <div>
                  <span className="font-medium text-paper/60">Title: </span>
                  <span className="text-paper">{inspectQuote.title}</span>
                </div>
              )}
              {inspectQuote.subreddit && (
                <div>
                  <span className="font-medium text-paper/60">Subreddit: </span>
                  <span className="text-paper">r/{inspectQuote.subreddit}</span>
                </div>
              )}
              {inspectQuote.author && (
                <div>
                  <span className="font-medium text-paper/60">Author: </span>
                  <span className="text-paper/80">{inspectQuote.author}</span>
                </div>
              )}
              <div>
                <span className="font-medium text-paper/60">Code applied: </span>
                <span className="font-semibold text-paper">{inspectQuote.code}</span>
              </div>
            </div>

            {/* Highlighted text pane */}
            <div className="flex-1 overflow-y-auto p-4 text-sm leading-relaxed whitespace-pre-wrap font-sans">
              {inspectQuote.content ? (
                <>
                  {inspectQuote.content.slice(0, inspectQuote.start_offset)}
                  <mark className="bg-paper text-ink font-semibold px-0.5">
                    {inspectQuote.quote ||
                      inspectQuote.content.slice(
                        inspectQuote.start_offset,
                        inspectQuote.end_offset
                      )}
                  </mark>
                  {inspectQuote.content.slice(inspectQuote.end_offset)}
                </>
              ) : (
                <div className="text-paper/60 italic">
                  Full source text not available.
                  <div className="mt-2 border-l-2 border-paper/40 pl-3">
                    &ldquo;{inspectQuote.quote}&rdquo;
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between border-t border-line p-3 bg-surface">
              <div className={meta}>
                Highlighted quote spans {inspectQuote.quote?.length || 0} characters
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  className={btnSm}
                  onClick={() => handleToggleStar(inspectQuote)}
                >
                  {inspectQuote.starred ? "★ Starred" : "☆ Star"}
                </button>
                <button
                  type="button"
                  className={`${btnSm} ${btnActive}`}
                  onClick={() => {
                    copyCitationToClipboard(inspectQuote);
                  }}
                >
                  Copy Citation
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Citation Configurator Dialog / Popover */}
      {citationModalQuote && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="citation-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-4"
          onClick={() => setCitationModalQuote(null)}
        >
          <div
            className="w-full max-w-lg border border-paper bg-ink p-5 shadow-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-line pb-2">
              <h3 id="citation-dialog-title" className="text-sm font-semibold">
                Copy Citation for Writing Draft
              </h3>
              <button
                type="button"
                className={btnSm}
                onClick={() => setCitationModalQuote(null)}
                aria-label="Close dialog"
              >
                ✕
              </button>
            </div>

            {/* Privacy & Field Configuration */}
            <div className="space-y-2 border border-line-soft bg-surface p-3 text-xs">
              <div className="font-semibold text-paper/80 uppercase text-[10px] tracking-wider mb-1">
                Attribution Fields (Privacy Guardrails)
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={citationOptions.includeCoder}
                  onChange={(e) =>
                    setCitationOptions((prev) => ({ ...prev, includeCoder: e.target.checked }))
                  }
                  className="rounded-none accent-paper"
                />
                <span>Include Coder Attribution ({citationModalQuote.coder})</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={citationOptions.includeOffsets}
                  onChange={(e) =>
                    setCitationOptions((prev) => ({ ...prev, includeOffsets: e.target.checked }))
                  }
                  className="rounded-none accent-paper"
                />
                <span>Include Character Offsets</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={citationOptions.includeNotes}
                  onChange={(e) =>
                    setCitationOptions((prev) => ({ ...prev, includeNotes: e.target.checked }))
                  }
                  className="rounded-none accent-paper"
                />
                <span>Include Attached Note</span>
              </label>

              <div className="border-t border-line-soft my-1.5 pt-1.5">
                <label className="flex items-center gap-2 cursor-pointer text-paper/90">
                  <input
                    type="checkbox"
                    checked={citationOptions.includeAuthor}
                    onChange={(e) =>
                      setCitationOptions((prev) => ({ ...prev, includeAuthor: e.target.checked }))
                    }
                    className="rounded-none accent-paper"
                  />
                  <span>Include Author name (Sensitive)</span>
                </label>
              </div>

              <div>
                <label className="flex items-center gap-2 cursor-pointer text-paper/90">
                  <input
                    type="checkbox"
                    checked={citationOptions.includeUrl}
                    onChange={(e) =>
                      setCitationOptions((prev) => ({ ...prev, includeUrl: e.target.checked }))
                    }
                    className="rounded-none accent-paper"
                  />
                  <span>Include URL / Link (Sensitive)</span>
                </label>
              </div>
            </div>

            {/* Preview */}
            <div>
              <div className="font-semibold text-paper/60 uppercase text-[10px] tracking-wider mb-1">
                Citation Preview
              </div>
              <pre className="border border-line bg-surface-raised p-3 text-xs text-paper whitespace-pre-wrap font-mono leading-relaxed overflow-x-auto">
                {formatCitation(citationModalQuote, citationOptions)}
              </pre>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-2 border-t border-line pt-3">
              <button
                type="button"
                className={btn}
                onClick={() => setCitationModalQuote(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`${btnPrimary}`}
                onClick={async () => {
                  await copyCitationToClipboard(citationModalQuote, citationOptions);
                  setCitationModalQuote(null);
                }}
              >
                Copy to Clipboard
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
