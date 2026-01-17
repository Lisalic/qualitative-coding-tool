import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import EntryModal from "./EntryModal";
import "../styles/DataTable.css";

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
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [projects, setProjects] = useState([]);
  const [targetDb, setTargetDb] = useState("");
  const MAX_SEARCH_FETCH = 100000000; // when searching, fetch up to this many rows

  const fetchEntries = async () => {
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
        String(currentDatabase) || ""
      );
      if (currentDatabase && isProjectSchema) {
        response = await apiFetch(
          `/api/file-entries/?limit=${fetchLimit}&offset=${offsetParam}&schema=${encodeURIComponent(
            String(currentDatabase)
          )}`
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
  };

  useEffect(() => {
    setCurrentDatabase(database);
    setPage(0);
  }, [database]);

  useEffect(() => {
    fetchEntries();
  }, [currentDatabase, limit, searchTerm, page]);

  // Clear selections when view changes (new DB, page, limit, or search)
  useEffect(() => {
    setSelectedItems(new Set());
  }, [currentDatabase, page, limit, searchTerm]);

  // Fetch user's projects for move target dropdown
  useEffect(() => {
    (async () => {
      try {
        const resp = await apiFetch(`/api/my-files/?file_type=raw_data`);
        if (resp.ok) {
          const data = await resp.json();
          setProjects(data.projects || []);
          // set default target if not set and there is another project
          if (!targetDb) {
            const other = (data.projects || []).find(
              (p) => p.schema_name !== currentDatabase
            );
            if (other) setTargetDb(other.schema_name);
          }
        }
      } catch (e) {
        // ignore
      }
    })();
  }, [currentDatabase]);

  const handleRowClick = (entry, type) => {
    setSelectedEntry({ ...entry, type });
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedEntry(null);
  };

  const deleteRow = async (table, id) => {
    if (!currentDatabase || !id) return;
    try {
      setLoading(true);
      const form = new FormData();
      form.append("schema", currentDatabase);
      form.append("table", table);
      form.append("row_id", id);

      const resp = await apiFetch(`/api/delete-row/`, {
        method: "POST",
        body: form,
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`Delete failed: ${resp.status} ${txt}`);
      }

      const data = await resp.json();
      if (data.error) throw new Error(data.error);

      // refresh entries
      await fetchEntries();
    } catch (err) {
      setError(`Error deleting row: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const displayDbName =
    currentDatabase && String(currentDatabase).trim()
      ? displayName || String(currentDatabase).replace(/\.db$/i, "")
      : title;

  let filteredSubmissions = [];
  let filteredComments = [];
  if (dbEntries) {
    const q = (searchTerm || "").trim().toLowerCase();
    const isSearchingLocal = (searchTerm || "").trim();
    if (q) {
      filteredSubmissions = (dbEntries.submissions || []).filter((sub) => {
        return (
          (sub.title && sub.title.toLowerCase().includes(q)) ||
          (sub.selftext && sub.selftext.toLowerCase().includes(q)) ||
          (sub.subreddit && sub.subreddit.toLowerCase().includes(q)) ||
          (sub.author && sub.author.toLowerCase().includes(q))
        );
      });
      filteredComments = (dbEntries.comments || []).filter((c) => {
        return (
          (c.body && c.body.toLowerCase().includes(q)) ||
          (c.subreddit && c.subreddit.toLowerCase().includes(q)) ||
          (c.author && c.author.toLowerCase().includes(q))
        );
      });
    } else {
      filteredSubmissions = dbEntries.submissions || [];
      filteredComments = dbEntries.comments || [];
    }

    if (Array.isArray(filteredSubmissions)) {
      if (isSearchingLocal) {
        const start = page * limit;
        filteredSubmissions = filteredSubmissions.slice(start, start + limit);
      } else {
        filteredSubmissions = filteredSubmissions.slice(0, limit);
      }
    }
    if (Array.isArray(filteredComments)) {
      if (isSearchingLocal) {
        const start = page * limit;
        filteredComments = filteredComments.slice(start, start + limit);
      } else {
        filteredComments = filteredComments.slice(0, limit);
      }
    }
  }

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

  const deleteSelected = async () => {
    if (!currentDatabase) return;
    const count = selectedItems.size;
    if (!count) return;
    if (!confirm(`Delete ${count} selected entries permanently?`)) return;

    try {
      setLoading(true);
      setError("");
      for (const k of Array.from(selectedItems)) {
        const parts = String(k).split(":");
        const type = parts[0];
        const id = parts.slice(1).join(":");
        const table = type === "submission" ? "submissions" : "comments";

        const form = new FormData();
        form.append("schema", currentDatabase);
        form.append("table", table);
        form.append("row_id", id);

        const resp = await apiFetch(`/api/delete-row/`, {
          method: "POST",
          body: form,
        });

        if (!resp.ok) {
          const txt = await resp.text();
          throw new Error(`Delete failed: ${resp.status} ${txt}`);
        }

        const data = await resp.json();
        if (data.error) throw new Error(data.error);
      }

      setSelectedItems(new Set());
      await fetchEntries();
    } catch (err) {
      setError(`Error deleting selected: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const moveSelected = async () => {
    if (!currentDatabase || !targetDb) return;
    if (targetDb === currentDatabase) {
      alert("Select a different target database");
      return;
    }
    if (selectedItems.size === 0) return;
    if (!confirm(`Move ${selectedItems.size} selected entries to ${targetDb}?`))
      return;

    // group by type
    const groups = { submission: [], comment: [] };
    for (const k of Array.from(selectedItems)) {
      const [type, ...rest] = k.split(":");
      const id = rest.join(":");
      if (type === "submission") groups.submission.push(id);
      else groups.comment.push(id);
    }

    try {
      setLoading(true);
      setError("");
      // For each non-empty group, call move endpoint
      for (const [typeKey, ids] of Object.entries(groups)) {
        if (!ids.length) continue;
        const table = typeKey === "submission" ? "submissions" : "comments";
        const resp = await apiFetch(`/api/move-rows/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_schema: currentDatabase,
            target_schema: targetDb,
            table,
            row_ids: ids,
          }),
        });

        if (!resp.ok) {
          const txt = await resp.text();
          throw new Error(`Move failed: ${resp.status} ${txt}`);
        }
      }

      setSelectedItems(new Set());
      await fetchEntries();
    } catch (err) {
      setError(`Error moving selected: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Selection helpers (for checkboxes)
  const keyFor = (type, id) => `${type}:${id}`;
  const isSelected = (type, id) => selectedItems.has(keyFor(type, id));
  const toggleSelection = (type, id, e) => {
    if (e && e.stopPropagation) e.stopPropagation();
    setSelectedItems((prev) => {
      const next = new Set(prev);
      const k = keyFor(type, id);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  };

  const toggleSelectAll = (type, list) => {
    const keys = (list || []).map((it) => keyFor(type, it.id));
    setSelectedItems((prev) => {
      const next = new Set(prev);
      const allSelected = keys.length > 0 && keys.every((k) => next.has(k));
      if (allSelected) {
        keys.forEach((k) => next.delete(k));
      } else {
        keys.forEach((k) => next.add(k));
      }
      return next;
    });
  };
  return (
    <div className="data-table-container">
      <div
        className="table-header"
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <h1 style={{ margin: 0, textAlign: "center" }}>
          {currentDatabase && String(currentDatabase).trim()
            ? `Database: ${displayDbName}`
            : title}
        </h1>
        {description ? (
          <div
            style={{
              width: "100%",
              textAlign: "center",
              color: "#cccccc",
              marginTop: 6,
            }}
          >
            {description}
          </div>
        ) : null}
      </div>

      {error && <p className="error-message">{error}</p>}

      {!dbEntries && !loading && !error && (
        <p className="info-message">Select a database to view its contents.</p>
      )}

      {loading && (
        <p className="loading-message">Loading database contents...</p>
      )}

      {dbEntries && (
        <>
          {/* Render metadata (counts/date) similarly to ManageDatabase */}
          {metadata && (
            <div
              className="database-metadata"
              style={{ marginBottom: "0.75rem" }}
            >
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

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "1rem",
              width: "100%",
            }}
          >
            <div
              style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}
            >
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
            <div style={{ display: "flex", alignItems: "center" }}>
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
            <p className="info-message">{dbEntries.message}</p>
          )}

          {filteredSubmissions.length > 0 && (
            <div className="table-section">
              <h3>Sample Posts ({limit})</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 48 }}>
                        <input
                          type="checkbox"
                          aria-label="select-all-submissions"
                          checked={
                            filteredSubmissions.length > 0 &&
                            filteredSubmissions.every((s) =>
                              selectedItems.has(keyFor("submission", s.id))
                            )
                          }
                          onChange={() =>
                            toggleSelectAll("submission", filteredSubmissions)
                          }
                        />
                      </th>
                      <th>ID</th>
                      {isFilteredView || currentDatabase === "filtered" ? (
                        <>
                          <th>Title</th>
                          <th>Selftext</th>
                          <th>Actions</th>
                        </>
                      ) : (
                        <>
                          <th>Subreddit</th>
                          <th>Title</th>
                          <th>Author</th>
                          <th>Score</th>
                          <th>Actions</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSubmissions.map((sub) => (
                      <tr
                        key={sub.id}
                        onClick={() => handleRowClick(sub, "submission")}
                        className="clickable-row"
                      >
                        <td>
                          <input
                            type="checkbox"
                            checked={isSelected("submission", sub.id)}
                            onChange={(e) =>
                              toggleSelection("submission", sub.id, e)
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        <td>{sub.id}</td>
                        {isFilteredView || currentDatabase === "filtered" ? (
                          <>
                            <td className="truncate">{sub.title}</td>
                            <td className="truncate">{sub.selftext}</td>
                            <td>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (!confirm("Delete this post permanently?"))
                                    return;
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
                            <td>{sub.subreddit}</td>
                            <td className="truncate">{sub.title}</td>
                            <td>{sub.author}</td>
                            <td>{sub.score}</td>
                            <td>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (!confirm("Delete this post permanently?"))
                                    return;
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
              <h3>Sample Comments ({limit})</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 48 }}>
                        <input
                          type="checkbox"
                          aria-label="select-all-comments"
                          checked={
                            filteredComments.length > 0 &&
                            filteredComments.every((c) =>
                              selectedItems.has(keyFor("comment", c.id))
                            )
                          }
                          onChange={() =>
                            toggleSelectAll("comment", filteredComments)
                          }
                        />
                      </th>
                      <th>ID</th>
                      <th>Subreddit</th>
                      <th>Body</th>
                      <th>Author</th>
                      <th>Score</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredComments.map((comment) => (
                      <tr
                        key={comment.id}
                        onClick={() => handleRowClick(comment, "comment")}
                        className="clickable-row"
                      >
                        <td>
                          <input
                            type="checkbox"
                            checked={isSelected("comment", comment.id)}
                            onChange={(e) =>
                              toggleSelection("comment", comment.id, e)
                            }
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        <td>{comment.id}</td>
                        <td>{comment.subreddit}</td>
                        <td className="truncate">{comment.body}</td>
                        <td>{comment.author}</td>
                        <td>{comment.score}</td>
                        <td>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              if (!confirm("Delete this comment permanently?"))
                                return;
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
              <p className="no-data">
                No data available. Please upload a file first.
              </p>
            )}

          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: "0.75rem",
              marginTop: "1rem",
            }}
          >
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

          <div
            style={{
              display: "flex",
              justifyContent: "center",
              marginTop: "0.5rem",
            }}
          >
            <button
              onClick={deleteSelected}
              className="btn btn-danger"
              disabled={selectedItems.size === 0 || loading}
            >
              Delete Selected ({selectedItems.size})
            </button>
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: "0.75rem",
              marginTop: "0.5rem",
            }}
          >
            <label style={{ color: "#fff", alignSelf: "center" }}>
              Move selected to:
            </label>
            <select
              value={targetDb}
              onChange={(e) => setTargetDb(e.target.value)}
              style={{ minWidth: 280 }}
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
                selectedItems.size === 0 ||
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
