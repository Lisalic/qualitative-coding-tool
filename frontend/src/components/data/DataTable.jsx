import { useEffect, useMemo, useState, useCallback } from "react";
import { apiFetch } from "../../api";
import EntryModal from "./EntryModal";
import { useDataTableActions } from "./useDataTableActions";
import "../../styles/DataTable.css";

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
    <div className="table-shell">
      <div className="panel-header layout-flex-col layout-center">
        <h1 className="heading-lg text-center">
          {currentDatabase && String(currentDatabase).trim()
            ? `Database: ${displayDbName}`
            : title}
        </h1>
        {description ? (
          <div className="text-muted text-center mt-md">
            {description}
          </div>
        ) : null}
      </div>

      {error && <p className="alert alert--error">{error}</p>}

      {!dbEntries && !loading && !error && (
        <p className="alert alert--info">Select a database to view its contents.</p>
      )}

      {loading && (
        <p className="alert alert--info">Loading database contents...</p>
      )}

      {dbEntries && (
        <>
          {/* Render metadata (counts/date) similarly to ManageDatabase */}
          {metadata && (
            <div className="database-metadata" style={{ marginBottom: "0.75rem" }}>
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
                      <div className="metadata-row">
                        <span>Posts: {submissions.toLocaleString()}</span>
                      </div>
                      <div className="metadata-row">
                        <span>Comments: {comments.toLocaleString()}</span>
                      </div>
                    </>
                  );
                })()
              ) : (
                <>
                  <div className="metadata-row">
                    <span>
                      Posts: {metadata.total_submissions?.toLocaleString() || 0}
                    </span>
                  </div>
                  <div className="metadata-row">
                    <span>
                      Comments: {metadata.total_comments?.toLocaleString() || 0}
                    </span>
                  </div>
                  {metadata.date_created && metadata.date_created > 0 && (
                    <div className="metadata-row">
                      <span>
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
                      </span>
                    </div>
                  )}
                </>
              )}
              {metadata.tables && metadata.created_at && (
                <div className="metadata-row">
                  <span>
                    Date Created:{" "}
                    {(() => {
                      try {
                        return new Date(metadata.created_at).toLocaleString();
                      } catch (e) {
                        return "Unknown";
                      }
                    })()}
                  </span>
                </div>
              )}
            </div>
          )}

          <div className="layout-flex-row layout-space-between" style={{ marginBottom: "1rem", width: "100%" }}>
            <div className="layout-flex-row gap-sm">
              <div className="limit-selector">
                <label htmlFor="entry-limit">Show entries: </label>
                <select
                  id="entry-limit"
                  value={limit}
                  onChange={(e) => {
                    setLimit(Number(e.target.value));
                    setPage(0);
                  }}
                  className="limit-select"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                  <option value={200}>200</option>
                </select>
              </div>
            </div>
            <div className="layout-flex-row">
              <input
                type="text"
                className="search-input"
                placeholder="Search posts/comments..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setPage(0);
                }}
                style={{ textAlign: "left" }}
              />
            </div>
          </div>

          {dbEntries.message && (
            <p className="alert alert--info">{dbEntries.message}</p>
          )}

          {filteredSubmissions.length > 0 && (
            <div className="table-section">
              <h3 className="table-section__title">Sample Posts ({limit})</h3>
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="table__th" style={{ width: 48 }}>
                        <input
                          type="checkbox"
                          aria-label="select-all-submissions"
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
                      <th className="table__th">ID</th>
                      {isFilteredView || currentDatabase === "filtered" ? (
                        <>
                          <th className="table__th">Title</th>
                          <th className="table__th">Selftext</th>
                          <th className="table__th">Actions</th>
                        </>
                      ) : (
                        <>
                          <th className="table__th">Subreddit</th>
                          <th className="table__th">Title</th>
                          <th className="table__th">Author</th>
                          <th className="table__th">Score</th>
                          <th className="table__th">Actions</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSubmissions.map((sub) => (
                      <tr
                        key={sub.id}
                        onClick={() => handleRowClick(sub, "submission")}
                        className="table__row--clickable table__row--hover"
                      >
                        <td className="table__td">
                          <input
                            type="checkbox"
                            checked={isSelected("submission", sub.id)}
                            onChange={(e) =>
                              toggleSelection("submission", sub.id, e)
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        <td className="table__td">{sub.id}</td>
                        {isFilteredView || currentDatabase === "filtered" ? (
                          <>
                            <td className="table__td truncate-cell">{sub.title}</td>
                            <td className="table__td truncate-cell">{sub.selftext}</td>
                            <td className="table__td">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  deleteRow("submissions", sub.id);
                                }}
                                className="btn btn-secondary"
                              >
                                Delete
                              </button>
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="table__td">{sub.subreddit}</td>
                            <td className="table__td truncate-cell">{sub.title}</td>
                            <td className="table__td">{sub.author}</td>
                            <td className="table__td">{sub.score}</td>
                            <td className="table__td">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  deleteRow("submissions", sub.id);
                                }}
                                className="btn btn-secondary"
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
            <div className="table-section">
              <h3 className="table-section__title">Sample Comments ({limit})</h3>
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th className="table__th" style={{ width: 48 }}>
                        <input
                          type="checkbox"
                          aria-label="select-all-comments"
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
                      <th className="table__th">ID</th>
                      <th className="table__th">Subreddit</th>
                      <th className="table__th">Body</th>
                      <th className="table__th">Author</th>
                      <th className="table__th">Score</th>
                      <th className="table__th">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredComments.map((comment) => (
                      <tr
                        key={comment.id}
                        onClick={() => handleRowClick(comment, "comment")}
                        className="table__row--clickable table__row--hover"
                      >
                        <td className="table__td">
                          <input
                            type="checkbox"
                            checked={isSelected("comment", comment.id)}
                            onChange={(e) =>
                              toggleSelection("comment", comment.id, e)
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        <td className="table__td">{comment.id}</td>
                        <td className="table__td">{comment.subreddit}</td>
                        <td className="table__td truncate-cell">{comment.body}</td>
                        <td className="table__td">{comment.author}</td>
                        <td className="table__td">{comment.score}</td>
                        <td className="table__td">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteRow("comments", comment.id);
                            }}
                            className="btn btn-secondary"
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
              <p className="empty-state">
                No data available. Please upload a file first.
              </p>
            )}

          <div className="layout-flex-row layout-center gap-sm" style={{ marginTop: "1rem" }}>
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="btn btn-secondary"
              disabled={page === 0}
            >
              Previous
            </button>
            <span style={{ minWidth: 80, textAlign: "center" }}>
              Page {page + 1}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              className="btn btn-secondary"
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

          <div className="layout-flex-row layout-center" style={{ marginTop: "0.5rem" }}>
            <button
              onClick={deleteSelected}
              className="btn btn-danger"
              disabled={selectedRows.size === 0 || loading}
            >
              Delete Selected ({selectedRows.size})
            </button>
          </div>
          <div className="layout-flex-row layout-center gap-sm" style={{ marginTop: "0.5rem" }}>
            <label className="text-primary" style={{ alignSelf: "center" }}>
              Move selected to:
            </label>
            <select
              value={targetDb}
              onChange={(e) => setTargetDb(e.target.value)}
              className="form__input"
              style={{ minWidth: 280, maxWidth: 320 }}
            >
              <option value="">-- select database --</option>
              {projects.map((p) => (
                <option key={p.schema_name} value={p.schema_name}>
                  {p.display_name || p.schema_name}
                </option>
              ))}
            </select>
            <button
              onClick={moveSelected}
              className="btn btn-secondary"
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
