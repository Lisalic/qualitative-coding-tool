import { useEffect, useMemo, useState, useCallback } from "react";
import { apiFetch } from "../../api";
import EntryModal from "./EntryModal";
import { useDataTableActions } from "./useDataTableActions";

const thClasses =
  "border-b-2 border-r border-paper px-3 py-2.5 text-left font-medium last:border-r-0";
const tdClasses =
  "border-b border-r border-paper/20 px-3 py-2.5 last:border-r-0";
const btnClasses =
  "border border-paper px-3 py-1.5 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";
const btnDangerClasses =
  "border border-error bg-error/10 px-3 py-1.5 text-sm text-error transition-colors hover:bg-error hover:text-paper disabled:opacity-40";

export default function DataTable({
  database = "",
  title = "Database Contents",
  isFilteredView = false,
  displayName = null,
  metadata = null,
  description = null,
}) {
  const [dbEntries, setDbEntries] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [currentDatabase, setCurrentDatabase] = useState(database);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [limit, setLimit] = useState(10);
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(0);
  const MAX_SEARCH_FETCH = 5000;

  const fetchEntries = useCallback(async () => {
    if (!currentDatabase || String(currentDatabase).trim() === "") {
      setDbEntries(null);
      setLoading(false);
      return;
    }

    try {
      setError("");
      setLoading(true);

      const isSearching = (searchTerm || "").trim();
      const fetchLimit = isSearching ? MAX_SEARCH_FETCH : limit;
      const offset = page * limit;
      const offsetParam = isSearching ? 0 : offset;
      let response;
      const isProjectSchema = /^proj_[A-Za-z0-9_]+(?:\.db)?$/.test(
        String(currentDatabase) || "",
      );
      if (currentDatabase && isProjectSchema) {
        response = await apiFetch(
          `/api/file-entries/?limit=${fetchLimit}&offset=${offsetParam}&schema=${encodeURIComponent(
            String(currentDatabase),
          )}`,
        );
      }

      if (!response.ok) {
        const text = await response.text();
        throw new Error(
          `Failed to fetch database entries: ${response.status} ${text || ""}`
        );
      }

      const data = await response.json();
      setDbEntries(data);
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [currentDatabase, limit, page, searchTerm]);

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
    deleteRow,
    deleteSelected,
    moveSelected,
  } = useDataTableActions({
    currentDatabase,
    fetchEntries,
    loading,
    setLoading,
    setError,
  });

  // Clear selections when view changes (new DB, page, limit, or search)
  useEffect(() => {
    setSelectedRows(new Set());
  }, [currentDatabase, page, limit, searchTerm, setSelectedRows]);

  const handleRowClick = (entry, type) => {
    setSelectedEntry({ ...entry, type });
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedEntry(null);
  };

  const displayDbName =
    currentDatabase && String(currentDatabase).trim()
      ? displayName || String(currentDatabase).replace(/\.db$/i, "")
      : title;

  const { filteredSubmissions, filteredComments } = useMemo(() => {
    if (!dbEntries) {
      return { filteredSubmissions: [], filteredComments: [] };
    }
    const q = (searchTerm || "").trim().toLowerCase();
    const isSearchingLocal = (searchTerm || "").trim();
    let submissions = dbEntries.submissions || [];
    let comments = dbEntries.comments || [];

    if (q) {
      submissions = submissions.filter((sub) => {
        return (
          (sub.title && sub.title.toLowerCase().includes(q)) ||
          (sub.selftext && sub.selftext.toLowerCase().includes(q)) ||
          (sub.subreddit && sub.subreddit.toLowerCase().includes(q)) ||
          (sub.author && sub.author.toLowerCase().includes(q))
        );
      });
      comments = comments.filter((c) => {
        return (
          (c.body && c.body.toLowerCase().includes(q)) ||
          (c.subreddit && c.subreddit.toLowerCase().includes(q)) ||
          (c.author && c.author.toLowerCase().includes(q))
        );
      });
    }

    if (Array.isArray(submissions)) {
      if (isSearchingLocal) {
        const start = page * limit;
        submissions = submissions.slice(start, start + limit);
      } else {
        submissions = submissions.slice(0, limit);
      }
    }
    if (Array.isArray(comments)) {
      if (isSearchingLocal) {
        const start = page * limit;
        comments = comments.slice(start, start + limit);
      } else {
        comments = comments.slice(0, limit);
      }
    }

    return {
      filteredSubmissions: submissions,
      filteredComments: comments,
    };
  }, [dbEntries, searchTerm, page, limit]);

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
    <div className="border border-paper p-8">
      <div className="mb-6 flex flex-col items-center">
        <h1 className="text-3xl font-bold">
          {currentDatabase && String(currentDatabase).trim()
            ? `Database: ${displayDbName}`
            : title}
        </h1>
        {description ? (
          <div className="mt-4 text-center text-paper/70">{description}</div>
        ) : null}
      </div>

      {error && (
        <p className="mb-4 border border-error bg-error/10 px-4 py-3 text-sm text-error">
          {error}
        </p>
      )}

      {!dbEntries && !loading && !error && (
        <p className="mb-4 border border-paper/20 bg-white/5 px-4 py-3 text-sm text-paper/70">
          Select a database to view its contents.
        </p>
      )}

      {loading && (
        <p className="mb-4 border border-paper/20 bg-white/5 px-4 py-3 text-sm text-paper/70">
          Loading database contents...
        </p>
      )}

      {dbEntries && (
        <>
          {metadata && (
            <div className="mb-3 text-sm text-paper/70">
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
                      Date Created:{" "}
                      {(() => {
                        try {
                          return new Date(
                            metadata.date_created * 1000
                          ).toLocaleString();
                        } catch (e) {
                          return "Unknown";
                        }
                      })()}
                    </div>
                  )}
                </>
              )}
              {metadata.tables && metadata.created_at && (
                <div>
                  Date Created:{" "}
                  {(() => {
                    try {
                      return new Date(metadata.created_at).toLocaleString();
                    } catch (e) {
                      return "Unknown";
                    }
                  })()}
                </div>
              )}
            </div>
          )}

          <div className="mb-4 flex w-full items-center justify-between">
            <div className="flex items-center gap-2">
              <label htmlFor="entry-limit" className="text-sm text-paper/70">
                Show entries:{" "}
              </label>
              <select
                id="entry-limit"
                value={limit}
                onChange={(e) => {
                  setLimit(Number(e.target.value));
                  setPage(0);
                }}
                className="border border-paper bg-white/5 px-2 py-1.5 text-sm text-paper focus:outline-none focus:ring-2 focus:ring-paper"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
              </select>
            </div>
            <div className="flex">
              <input
                type="text"
                placeholder="Search posts/comments..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setPage(0);
                }}
                className="border border-paper bg-white/5 px-3 py-1.5 text-left text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper"
              />
            </div>
          </div>

          {dbEntries.message && (
            <p className="mb-4 border border-paper/20 bg-white/5 px-4 py-3 text-sm text-paper/70">
              {dbEntries.message}
            </p>
          )}

          {filteredSubmissions.length > 0 && (
            <div className="mb-8">
              <h3 className="mb-3 text-lg font-medium">Sample Posts ({limit})</h3>
              <div className="overflow-x-auto border border-paper">
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className={thClasses} style={{ width: 48 }}>
                        <input
                          type="checkbox"
                          aria-label="select-all-submissions"
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
                          <th className={thClasses}>Actions</th>
                        </>
                      ) : (
                        <>
                          <th className={thClasses}>Subreddit</th>
                          <th className={thClasses}>Title</th>
                          <th className={thClasses}>Author</th>
                          <th className={thClasses}>Score</th>
                          <th className={thClasses}>Actions</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSubmissions.map((sub) => (
                      <tr
                        key={sub.id}
                        onClick={() => handleRowClick(sub, "submission")}
                        className="cursor-pointer transition-colors hover:bg-white/5"
                      >
                        <td className={tdClasses}>
                          <input
                            type="checkbox"
                            className="accent-paper"
                            checked={isSelected("submission", sub.id)}
                            onChange={(e) =>
                              toggleSelection("submission", sub.id, e)
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        <td className={tdClasses}>{sub.id}</td>
                        {isFilteredView || currentDatabase === "filtered" ? (
                          <>
                            <td className={`${tdClasses} max-w-[300px] truncate`}>
                              {sub.title}
                            </td>
                            <td className={`${tdClasses} max-w-[300px] truncate`}>
                              {sub.selftext}
                            </td>
                            <td className={tdClasses}>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  deleteRow("submissions", sub.id);
                                }}
                                className={btnClasses}
                              >
                                Delete
                              </button>
                            </td>
                          </>
                        ) : (
                          <>
                            <td className={tdClasses}>{sub.subreddit}</td>
                            <td className={`${tdClasses} max-w-[300px] truncate`}>
                              {sub.title}
                            </td>
                            <td className={tdClasses}>{sub.author}</td>
                            <td className={tdClasses}>{sub.score}</td>
                            <td className={tdClasses}>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  deleteRow("submissions", sub.id);
                                }}
                                className={btnClasses}
                              >
                                Delete
                              </button>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {filteredComments.length > 0 && (
            <div className="mb-8">
              <h3 className="mb-3 text-lg font-medium">Sample Comments ({limit})</h3>
              <div className="overflow-x-auto border border-paper">
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className={thClasses} style={{ width: 48 }}>
                        <input
                          type="checkbox"
                          aria-label="select-all-comments"
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
                      <th className={thClasses}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredComments.map((comment) => (
                      <tr
                        key={comment.id}
                        onClick={() => handleRowClick(comment, "comment")}
                        className="cursor-pointer transition-colors hover:bg-white/5"
                      >
                        <td className={tdClasses}>
                          <input
                            type="checkbox"
                            className="accent-paper"
                            checked={isSelected("comment", comment.id)}
                            onChange={(e) =>
                              toggleSelection("comment", comment.id, e)
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        <td className={tdClasses}>{comment.id}</td>
                        <td className={tdClasses}>{comment.subreddit}</td>
                        <td className={`${tdClasses} max-w-[300px] truncate`}>
                          {comment.body}
                        </td>
                        <td className={tdClasses}>{comment.author}</td>
                        <td className={tdClasses}>{comment.score}</td>
                        <td className={tdClasses}>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteRow("comments", comment.id);
                            }}
                            className={btnClasses}
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {dbEntries.submissions.length === 0 &&
            dbEntries.comments.length === 0 && (
              <p className="border border-paper/20 bg-white/[0.02] px-4 py-6 text-center italic text-paper/70">
                No data available. Please upload a file first.
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
            <select
              value={targetDb}
              onChange={(e) => setTargetDb(e.target.value)}
              className="min-w-[280px] max-w-[320px] border border-paper bg-white/5 px-2 py-1.5 text-sm text-paper focus:outline-none focus:ring-2 focus:ring-paper"
            >
              <option value="">-- select database --</option>
              {projects.map((p) => (
                <option key={p.schema_name} value={p.schema_name}>
                  {p.display_name || p.schema_name}
                </option>
              ))}
            </select>
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
      />
    </div>
  );
}
