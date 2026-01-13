import { useState, useEffect } from "react";
import { apiFetch } from "../api";

export default function CodebookManager({ onViewCodebook }) {
  const [codebooks, setCodebooks] = useState([]);
  const [renamingCb, setRenamingCb] = useState(null);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCodebooks();
  }, []);

  const fetchCodebooks = async () => {
    try {
      const response = await apiFetch("/api/list-codebooks");
      if (!response.ok) throw new Error("Failed to fetch codebooks");
      const data = await response.json();
      // ensure metadata fields exist for each codebook
      const raw = (data.codebooks || []).map((cb) => ({
        ...cb,
        metadata: cb.metadata || {},
      }));

      // For project-backed codebooks, fetch the project's content_store to compute accurate character counts
      const enriched = await Promise.all(
        raw.map(async (cb) => {
          if (cb.source === "project") {
            const schema = cb.metadata?.schema || cb.schema_name || cb.id;
            try {
              const resp = await apiFetch(
                `/api/codebook?codebook_id=${encodeURIComponent(schema)}`
              );
              if (resp.ok) {
                const j = await resp.json();
                const content = j.codebook || "";
                const updatedMeta = { ...cb.metadata };
                updatedMeta.characters = content.length;
                return { ...cb, metadata: updatedMeta, content };
              }
            } catch (err) {
              // ignore fetch error and return cb as-is
              console.error("Failed to fetch project codebook content:", err);
            }
          }
          return cb;
        })
      );

      setCodebooks(enriched);
    } catch (err) {
      console.error("Error fetching codebooks:", err);
      setError("Failed to load codebooks");
    }
  };

  const handleRenameCodebook = async (oldId) => {
    if (!newName.trim()) {
      setError("New ID cannot be empty");
      return;
    }
    // find the codebook object
    const cb = codebooks.find(
      (c) => c.id === oldId || String(c.id) === String(oldId)
    );
    try {
      if (cb && cb.source === "project") {
        const formData = new FormData();
        const schema =
          cb.metadata?.schema || cb.schema_name || cb.metadata?.schema_name;
        if (!schema)
          throw new Error("Project schema name not found for rename");
        formData.append("schema_name", schema);
        formData.append("display_name", newName.trim());
        if (newDescription && newDescription.trim()) {
          formData.append("description", newDescription.trim());
        }

        const response = await apiFetch("/api/rename-project/", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) throw new Error("Failed to rename project");
      }

      setRenamingCb(null);
      setNewName("");
      fetchCodebooks();
    } catch (err) {
      console.error("Rename error:", err);
      setError(`Error renaming codebook: ${err.message}`);
    }
  };

  const handleDeleteCodebook = async (cbId) => {
    try {
      const cb = codebooks.find(
        (c) => c.id === cbId || String(c.id) === String(cbId)
      );
      if (cb && cb.source === "project") {
        // delete project schema (with auth)
        const schema =
          cb.metadata?.schema ||
          cb.schema_name ||
          cb.metadata?.schema_name ||
          cb.id;
        const response = await apiFetch(
          `/api/delete-database/${encodeURIComponent(schema)}`,
          {
            method: "DELETE",
          }
        );
        if (!response.ok) throw new Error("Failed to delete project schema");
      } else {
        // fallback to file-based deletion endpoint (try to delete this later maybe)
        const response = await apiFetch(`/api/delete-codebook/${cbId}`, {
          method: "DELETE",
        });
        if (!response.ok) throw new Error("Failed to delete codebook file");
      }

      fetchCodebooks();
    } catch (err) {
      console.error("Delete error:", err);
      setError(`Error deleting codebook: ${err.message}`);
    }
  };

  const startRename = (cbId) => {
    setRenamingCb(cbId);
    const cb = codebooks.find(
      (c) => c.id === cbId || String(c.id) === String(cbId)
    );
    setNewName(cb?.name || cb?.display_name || String(cbId));
    setNewDescription(cb?.description || cb?.metadata?.description || "");
  };

  const cancelRename = () => {
    setRenamingCb(null);
    setNewName("");
    setNewDescription("");
  };

  const formatMetaText = (cb) => {
    // prefer explicit metadata.characters (or variants)
    const meta = cb.metadata || {};
    const metaChars = meta.characters ?? meta.char_count ?? meta.chars ?? null;
    const charCount =
      metaChars != null
        ? metaChars
        : cb.content?.length ?? cb.codebook?.length ?? cb.text?.length ?? null;

    const date =
      meta.date_created && meta.date_created > 0
        ? (() => {
            try {
              return new Date(meta.date_created * 1000).toLocaleString();
            } catch (e) {
              return null;
            }
          })()
        : null;

    if (charCount == null && !date) return "No metadata available";

    const parts = [];
    if (charCount != null)
      parts.push(`${charCount.toLocaleString()} characters`);
    if (date) parts.push(date);
    return parts.join(" • ");
  };

  const getCharText = (cb) => {
    const meta = cb.metadata || {};
    const metaChars = meta.characters ?? meta.char_count ?? meta.chars ?? null;
    const charCount =
      metaChars != null
        ? metaChars
        : cb.content?.length ?? cb.codebook?.length ?? cb.text?.length ?? 0;
    return `${charCount.toLocaleString()} characters`;
  };

  const getDateText = (cb) => {
    const meta = cb.metadata || {};
    const ts = meta.date_created;
    if (!ts || ts <= 0) return "";
    try {
      return new Date(ts * 1000).toLocaleString();
    } catch (e) {
      return "Unknown";
    }
  };

  return (
    <div>
      {codebooks.length > 0 && (
        <div className="database-section">
          <div className="database-selection">
            <h1
              style={{
                textAlign: "center",
                fontSize: "28px",
                fontWeight: "600",
                margin: "0 0 30px 0",
              }}
            >
              Manage Codebooks
            </h1>
            <div className="database-list">
              {codebooks.map((cb) => (
                <div key={cb.id} className="database-item">
                  {renamingCb === cb.id ? (
                    <div className="rename-controls">
                      <input
                        type="text"
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleRenameCodebook(cb.id);
                          if (e.key === "Escape") cancelRename();
                        }}
                        placeholder="New ID (number)"
                        autoFocus
                      />
                      <textarea
                        placeholder="Optional description..."
                        value={newDescription}
                        onChange={(e) => setNewDescription(e.target.value)}
                        rows={3}
                        style={{
                          width: "100%",
                          marginTop: "8px",
                          padding: "8px",
                          backgroundColor: "#000",
                          color: "#fff",
                          border: "1px solid #fff",
                          borderRadius: "4px",
                          fontSize: "14px",
                          resize: "vertical",
                        }}
                      />
                      <button onClick={() => handleRenameCodebook(cb.id)}>
                        Save
                      </button>
                      <button onClick={cancelRename}>Cancel</button>
                    </div>
                  ) : (
                    <>
                      <div className="database-info">
                        <strong>{cb.name || cb.display_name || cb.id}</strong>
                        <div className="database-description">
                          {cb.description ?? cb.metadata?.description ?? "null"}
                        </div>
                        <div className="database-metadata">
                          <div className="metadata-row">
                            <span>{getCharText(cb)}</span>
                          </div>
                          <div className="metadata-row">
                            <span>{getDateText(cb)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="database-actions">
                        <button
                          onClick={() => onViewCodebook(cb.id)}
                          style={{
                            backgroundColor: "#000000",
                            color: "#ffffff",
                            border: "1px solid #ffffff",
                            padding: "12px 24px",
                            fontSize: "16px",
                            cursor: "pointer",
                            borderRadius: "4px",
                            transition: "all 0.2s",
                            marginRight: "10px",
                          }}
                          onMouseOver={(e) => {
                            e.target.style.backgroundColor = "#ffffff";
                            e.target.style.color = "#000000";
                          }}
                          onMouseOut={(e) => {
                            e.target.style.backgroundColor = "#000000";
                            e.target.style.color = "#ffffff";
                          }}
                        >
                          View
                        </button>
                        <button
                          onClick={() => startRename(cb.id)}
                          style={{
                            backgroundColor: "#000000",
                            color: "#ffffff",
                            border: "1px solid #ffffff",
                            padding: "12px 24px",
                            fontSize: "16px",
                            cursor: "pointer",
                            borderRadius: "4px",
                            transition: "all 0.2s",
                            marginRight: "10px",
                          }}
                          onMouseOver={(e) => {
                            e.target.style.backgroundColor = "#ffffff";
                            e.target.style.color = "#000000";
                          }}
                          onMouseOut={(e) => {
                            e.target.style.backgroundColor = "#000000";
                            e.target.style.color = "#ffffff";
                          }}
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            if (
                              confirm(
                                `Are you sure you want to delete "${cb.name}"?`
                              )
                            ) {
                              handleDeleteCodebook(cb.id);
                            }
                          }}
                          style={{
                            backgroundColor: "#000000",
                            color: "#ffffff",
                            border: "1px solid #ffffff",
                            padding: "12px 24px",
                            fontSize: "16px",
                            cursor: "pointer",
                            borderRadius: "4px",
                            transition: "all 0.2s",
                          }}
                          onMouseOver={(e) => {
                            e.target.style.backgroundColor = "#ffffff";
                            e.target.style.color = "#000000";
                          }}
                          onMouseOut={(e) => {
                            e.target.style.backgroundColor = "#000000";
                            e.target.style.color = "#ffffff";
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {error && (
        <div
          style={{
            color: "#ff6666",
            padding: "10px",
            border: "1px solid #ff6666",
            borderRadius: "4px",
            marginTop: "10px",
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}
