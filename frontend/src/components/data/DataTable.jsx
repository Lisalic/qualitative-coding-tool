import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { apiFetch } from "../../api";
import EntryModal from "./EntryModal";
import { useDataTableActions } from "./useDataTableActions";
import { useRowMemos } from "./useRowMemos";
import MemoIndicator from "./MemoIndicator";
import Panel from "../shell/Panel";
import Dropdown from "../primitives/Dropdown";
import { btn, btnDanger, input, select } from "../../lib/uiClasses";
import { PAGE_SIZE_OPTIONS } from "../../lib/pageSizes";
import { formatDate } from "../../lib/formatDate";

// The header row sticks to the top of the Panel's own scroll container, so a
// long page of rows stays readable without a separate frozen-header widget.
const thClasses =
  "sticky top-0 z-[1] border-b-2 border-r border-paper bg-ink px-3 py-2 text-left font-medium last:border-r-0";
const tdClasses =
  "border-b border-r border-line-soft px-3 py-2 last:border-r-0";
const btnClasses = btn;
const btnDangerClasses = btnDanger;
const inputClasses = input;
const selectClasses = select;

export default function DataTable({
  database = "",
  isFilteredView = false,
  metadata = null,
}) {
  const [dbEntries, setDbEntries] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [currentDatabase, setCurrentDatabase] = useState(database);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [limit, setLimit] = useState(10);
  const [searchTerm, setSearchTerm] = useState("");
  // What the server is asked to search for: the box's text once typing
  // pauses, so a search isn't a request per keystroke.
  const [appliedSearch, setAppliedSearch] = useState("");
  const [page, setPage] = useState(0);
  const latestRequest = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => setAppliedSearch(searchTerm.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const fetchEntries = useCallback(async () => {
    const isProjectSchema = /^proj_[A-Za-z0-9_]+(?:\.db)?$/.test(String(currentDatabase || ""));
    if (!isProjectSchema) {
      setDbEntries(null);
      setLoading(false);
      return;
    }

    // Only the newest request may update the table: an older, slower
    // response (a previous page or search) must not overwrite it.
    const requestId = ++latestRequest.current;
    try {
      setError("");
      setLoading(true);

      // Search runs server-side over every row; the page is a page of matches.
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(page * limit),
        schema: String(currentDatabase),
      });
      if (appliedSearch) params.set("q", appliedSearch);
      const response = await apiFetch(`/api/file-entries/?${params}`);

      if (!response.ok) {
        throw new Error(
          response.status === 404
            ? "This database no longer exists."
            : `Couldn't load the rows (HTTP ${response.status}). Please try again.`,
        );
      }

      const data = await response.json();
      if (requestId === latestRequest.current) setDbEntries(data);
    } catch (err) {
      if (requestId === latestRequest.current) setError(`Error: ${err.message}`);
    } finally {
      if (requestId === latestRequest.current) setLoading(false);
    }
  }, [appliedSearch, currentDatabase, limit, page]);

  useEffect(() => {
    setCurrentDatabase(database);
    setPage(0);
  }, [database]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const {
    selectedRows,
    setSelectedRows,
    projects,
    targetDb,
    setTargetDb,
    keyFor,
    isSelected,
    toggleSelection,
    toggleSelectAll,
    deleteSelected,
    moveSelected,
  } = useDataTableActions({
    currentDatabase,
    fetchEntries,
    loading,
    setLoading,
    setError,
  });
  const { getMemo, saveMemo } = useRowMemos(currentDatabase);

  const targetDbOptions = useMemo(
    () =>
      projects.map((p) => ({
        value: p.schema_name,
        label: p.display_name || p.schema_name,
      })),
    [projects],
  );

  // Clear selections only when switching databases. Page, page size, and search
  // changes intentionally do NOT clear selection, so it persists across them.
  useEffect(() => {
    setSelectedRows(new Set());
  }, [currentDatabase, setSelectedRows]);

  const handleRowClick = (entry, type) => {
    setSelectedEntry({ ...entry, type });
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedEntry(null);
  };

  const { filteredSubmissions, filteredComments } = useMemo(
    () => ({
      filteredSubmissions: dbEntries?.submissions || [],
      filteredComments: dbEntries?.comments || [],
    }),
    [dbEntries],
  );

  const pageCount = dbEntries
    ? Math.ceil(Math.max(dbEntries.total_submissions || 0, dbEntries.total_comments || 0) / limit)
    : 0;

  // Helpers for modal navigation
  let currentList = [];
  if (selectedEntry) {
    if (selectedEntry.type === "submission") {
      currentList = filteredSubmissions || [];
    } else {
      currentList = filteredComments || [];
    }
  }

  const currentIndex = selectedEntry
    ? currentList.findIndex((it) => String(it.id) === String(selectedEntry.id))
    : -1;

  const goToPrev = () => {
    if (currentIndex > 0) {
      const prev = currentList[currentIndex - 1];
      setSelectedEntry({ ...prev, type: selectedEntry.type });
    }
  };

  const goToNext = () => {
    if (currentIndex >= 0 && currentIndex < currentList.length - 1) {
      const next = currentList[currentIndex + 1];
      setSelectedEntry({ ...next, type: selectedEntry.type });
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {error && (
        <p className="border border-error bg-error/10 px-3 py-2 text-sm text-error">
          {error}
        </p>
      )}

      {!dbEntries && !loading && !error && (
        <p className="border border-line bg-surface-raised px-3 py-2 text-sm text-paper/70">
          Select a database to view its contents.
        </p>
      )}

      {loading && (
        <p className="border border-line bg-surface-raised px-3 py-2 text-sm text-paper/70">
          Loading database contents...
        </p>
      )}

      {dbEntries && (
        <>
          {metadata && (
            <div className="text-sm text-paper/70">
              {metadata.tables ? (
                (() => {
                  const submissions =
                    metadata.tables.find((t) => t.table_name === "submissions")
                      ?.row_count || 0;
                  const comments =
                    metadata.tables.find((t) => t.table_name === "comments")
                      ?.row_count || 0;
                  return (
                    <>
                      <div>Posts: {submissions.toLocaleString()}</div>
                      <div>Comments: {comments.toLocaleString()}</div>
                    </>
                  );
                })()
              ) : (
                <>
                  <div>
                    Posts: {metadata.total_submissions?.toLocaleString() || 0}
                  </div>
                  <div>
                    Comments: {metadata.total_comments?.toLocaleString() || 0}
                  </div>
                  {metadata.date_created && metadata.date_created > 0 && (
                    <div>
                      Date created: {formatDate(metadata.date_created * 1000) || "Unknown"}
                    </div>
                  )}
                </>
              )}
              {metadata.tables && metadata.created_at && (
                <div>
                  Date created: {formatDate(metadata.created_at) || "Unknown"}
                </div>
              )}
            </div>
          )}

          <div className="flex w-full flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {/* The option labels read "25 / page", so a separate
                  "Show entries:" label would just say it twice. */}
              <Dropdown
                id="entry-limit"
                value={limit}
                options={PAGE_SIZE_OPTIONS}
                onChange={(next) => {
                  setLimit(next);
                  setPage(0);
                }}
                triggerClassName={`w-auto ${selectClasses}`}
                listLabel="Entries per page"
              />
            </div>
            <div className="flex">
              <input
                type="text"
                placeholder="Search posts and comments…"
                aria-label="Search posts and comments"
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setPage(0);
                }}
                className={`${inputClasses} text-left`}
              />
            </div>
          </div>

          {dbEntries.message && (
            <p className="border border-line bg-surface-raised px-3 py-2 text-sm text-paper/70">
              {dbEntries.message}
            </p>
          )}

          {filteredSubmissions.length > 0 && (
            <Panel
              title={`Posts (${(dbEntries.total_submissions ?? filteredSubmissions.length).toLocaleString()})`}
              padded={false}
              bodyClassName="overflow-auto"
            >
              <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className={thClasses} style={{ width: 48 }}>
                        <input
                          type="checkbox"
                          aria-label="Select all posts on this page"
                          className="accent-paper"
                          checked={
                            filteredSubmissions.length > 0 &&
                            filteredSubmissions.every((s) =>
                              selectedRows.has(keyFor("submission", s.id))
                            )
                          }
                          onChange={() =>
                            toggleSelectAll("submission", filteredSubmissions)
                          }
                        />
                      </th>
                      <th className={thClasses}>ID</th>
                      {isFilteredView || currentDatabase === "filtered" ? (
                        <>
                          <th className={thClasses}>Title</th>
                          <th className={thClasses}>Selftext</th>
                        </>
                      ) : (
                        <>
                          <th className={thClasses}>Subreddit</th>
                          <th className={thClasses}>Title</th>
                          <th className={thClasses}>Author</th>
                          <th className={thClasses}>Score</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSubmissions.map((sub) => (
                      <tr
                        key={sub.id}
                        tabIndex={0}
                        aria-label={`Open post ${sub.id}`}
                        onClick={() => handleRowClick(sub, "submission")}
                        onKeyDown={(e) => {
                          if (e.target !== e.currentTarget) return;
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            handleRowClick(sub, "submission");
                          }
                        }}
                        className="cursor-pointer transition-colors hover:bg-white/5"
                      >
                        <td className={tdClasses}>
                          <input
                            type="checkbox"
                            className="accent-paper"
                            checked={isSelected("submission", sub.id)}
                            aria-label={`Select post ${sub.id}`}
                            onChange={(e) =>
                              toggleSelection("submission", sub.id, e)
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        <td className={tdClasses}>
                          {sub.id}
                          <MemoIndicator memo={getMemo("submission", sub.id)} />
                        </td>
                        {isFilteredView || currentDatabase === "filtered" ? (
                          <>
                            <td className={`${tdClasses} max-w-[42ch] truncate`} title={sub.title}>
                              {sub.title}
                            </td>
                            <td className={`${tdClasses} max-w-[42ch] truncate`} title={sub.selftext}>
                              {sub.selftext}
                            </td>
                          </>
                        ) : (
                          <>
                            <td className={tdClasses}>{sub.subreddit}</td>
                            <td className={`${tdClasses} max-w-[42ch] truncate`} title={sub.title}>
                              {sub.title}
                            </td>
                            <td className={tdClasses}>{sub.author}</td>
                            <td className={tdClasses}>{sub.score}</td>
                          </>
                        )}
                      </tr>
                    ))}
                </tbody>
              </table>
            </Panel>
          )}

          {filteredComments.length > 0 && (
            <Panel
              title={`Comments (${(dbEntries.total_comments ?? filteredComments.length).toLocaleString()})`}
              padded={false}
              bodyClassName="overflow-auto"
            >
              <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className={thClasses} style={{ width: 48 }}>
                        <input
                          type="checkbox"
                          aria-label="Select all comments on this page"
                          className="accent-paper"
                          checked={
                            filteredComments.length > 0 &&
                            filteredComments.every((c) =>
                              selectedRows.has(keyFor("comment", c.id))
                            )
                          }
                          onChange={() =>
                            toggleSelectAll("comment", filteredComments)
                          }
                        />
                      </th>
                      <th className={thClasses}>ID</th>
                      <th className={thClasses}>Subreddit</th>
                      <th className={thClasses}>Body</th>
                      <th className={thClasses}>Author</th>
                      <th className={thClasses}>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredComments.map((comment) => (
                      <tr
                        key={comment.id}
                        tabIndex={0}
                        aria-label={`Open comment ${comment.id}`}
                        onClick={() => handleRowClick(comment, "comment")}
                        onKeyDown={(e) => {
                          if (e.target !== e.currentTarget) return;
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            handleRowClick(comment, "comment");
                          }
                        }}
                        className="cursor-pointer transition-colors hover:bg-white/5"
                      >
                        <td className={tdClasses}>
                          <input
                            type="checkbox"
                            className="accent-paper"
                            checked={isSelected("comment", comment.id)}
                            aria-label={`Select comment ${comment.id}`}
                            onChange={(e) =>
                              toggleSelection("comment", comment.id, e)
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        <td className={tdClasses}>
                          {comment.id}
                          <MemoIndicator memo={getMemo("comment", comment.id)} />
                        </td>
                        <td className={tdClasses}>{comment.subreddit}</td>
                        <td className={`${tdClasses} max-w-[42ch] truncate`} title={comment.body}>
                          {comment.body}
                        </td>
                        <td className={tdClasses}>{comment.author}</td>
                        <td className={tdClasses}>{comment.score}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </Panel>
          )}

          {dbEntries.submissions.length === 0 &&
            dbEntries.comments.length === 0 && (
              <p className="border border-line bg-surface px-4 py-6 text-center italic text-paper/70">
                {appliedSearch ? `No rows match "${appliedSearch}".` : "This database has no rows."}
              </p>
            )}

          <div className="mt-4 flex items-center justify-center gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className={btnClasses}
              disabled={page === 0}
            >
              Previous
            </button>
            <span className="min-w-[80px] text-center text-sm">
              Page {page + 1}
              {pageCount > 0 ? ` of ${pageCount}` : ""}
            </span>
            <button
              type="button"
              onClick={() => setPage((p) => p + 1)}
              className={btnClasses}
              disabled={
                !dbEntries ||
                !(
                  (dbEntries.total_submissions || 0) > (page + 1) * limit ||
                  (dbEntries.total_comments || 0) > (page + 1) * limit
                )
              }
            >
              Next
            </button>
          </div>

          <div className="mt-2 flex justify-center">
            <button
              type="button"
              onClick={deleteSelected}
              className={btnDangerClasses}
              disabled={selectedRows.size === 0 || loading}
            >
              Delete Selected ({selectedRows.size})
            </button>
          </div>
          <div className="mt-2 flex items-center justify-center gap-2">
            <label className="text-sm">Move selected to:</label>
            <Dropdown
              value={targetDb}
              options={targetDbOptions}
              onChange={setTargetDb}
              placeholder="Select a database"
              triggerClassName={`min-w-[280px] max-w-[320px] ${selectClasses}`}
              listLabel="Destination database"
              searchPlaceholder="Search databases…"
              emptyMessage="No databases match that search."
            />
            <button
              type="button"
              onClick={moveSelected}
              className={btnClasses}
              disabled={
                selectedRows.size === 0 ||
                !targetDb ||
                targetDb === currentDatabase ||
                loading
              }
            >
              Move Selected
            </button>
          </div>
        </>
      )}

      <EntryModal
        entry={selectedEntry}
        isOpen={showModal}
        onClose={closeModal}
        database={currentDatabase}
        onPrev={goToPrev}
        onNext={goToNext}
        hasPrev={currentIndex > 0}
        hasNext={currentIndex >= 0 && currentIndex < currentList.length - 1}
        memo={selectedEntry ? getMemo(selectedEntry.type, selectedEntry.id) : null}
        onSaveMemo={saveMemo}
      />
    </div>
  );
}
