import { useEffect, useState } from "react";
import EntryModal from "./EntryModal";
import "../styles/DataTable.css";

export default function DataTable({
  database = "",
  title = "Database Contents",
  isFilteredView = false,
  displayName = null,
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

      const fetchLimit = (searchTerm || "").trim() ? MAX_SEARCH_FETCH : limit;
      let response;
      // If this 'database' looks like a project schema (created as proj_<id> or proj_<id>.db)
      const isProjectSchema = /^proj_[A-Za-z0-9_]+(?:\.db)?$/.test(
        String(currentDatabase) || ""
      );
      if (currentDatabase && isProjectSchema) {
        response = await fetch(
          `/api/project-entries/?limit=${fetchLimit}&schema=${encodeURIComponent(
            String(currentDatabase)
          )}`,
          { credentials: "include" }
        );
      } else {
        response = await fetch(
          `/api/database-entries/?limit=${fetchLimit}&database=${encodeURIComponent(
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
  }, [database]);

  useEffect(() => {
    fetchEntries();
  }, [currentDatabase, limit, searchTerm]);

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

  let filteredSubmissions = [];
  let filteredComments = [];
  if (dbEntries) {
    const q = (searchTerm || "").trim().toLowerCase();
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
    // Limit displayed results to the requested `limit`
    if (Array.isArray(filteredSubmissions)) {
      filteredSubmissions = filteredSubmissions.slice(0, limit);
    }
    if (Array.isArray(filteredComments)) {
      filteredComments = filteredComments.slice(0, limit);
    }
  }

  return (
    <div className="data-table-container">
      <div
        className="table-header"
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <h1 style={{ margin: 0, textAlign: "center" }}>
          {currentDatabase && String(currentDatabase).trim()
            ? `Database: ${displayDbName}`
            : title}
        </h1>
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
                    <span>Posts: {metadata.total_submissions?.toLocaleString() || 0}</span>
                  </div>
                  <div className="metadata-row">
                    <span>Comments: {metadata.total_comments?.toLocaleString() || 0}</span>
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
                  onChange={(e) => setLimit(Number(e.target.value))}
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
                onChange={(e) => setSearchTerm(e.target.value)}
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
                      <th>ID</th>
                      {isFilteredView || currentDatabase === "filtered" ? (
                        <>
                          <th>Title</th>
                          <th>Selftext</th>
                        </>
                      ) : (
                        <>
                          <th>Subreddit</th>
                          <th>Title</th>
                          <th>Author</th>
                          <th>Score</th>
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
                        <td>{sub.id}</td>
                        {isFilteredView || currentDatabase === "filtered" ? (
                          <>
                            <td className="truncate">{sub.title}</td>
                            <td className="truncate">{sub.selftext}</td>
                          </>
                        ) : (
                          <>
                            <td>{sub.subreddit}</td>
                            <td className="truncate">{sub.title}</td>
                            <td>{sub.author}</td>
                            <td>{sub.score}</td>
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
                      <th>ID</th>
                      <th>Subreddit</th>
                      <th>Body</th>
                      <th>Author</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredComments.map((comment) => (
                      <tr
                        key={comment.id}
                        onClick={() => handleRowClick(comment, "comment")}
                        className="clickable-row"
                      >
                        <td>{comment.id}</td>
                        <td>{comment.subreddit}</td>
                        <td className="truncate">{comment.body}</td>
                        <td>{comment.author}</td>
                        <td>{comment.score}</td>
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
        </>
      )}

      <EntryModal
        entry={selectedEntry}
        isOpen={showModal}
        onClose={closeModal}
        database={currentDatabase}
      />
    </div>
  );
}
