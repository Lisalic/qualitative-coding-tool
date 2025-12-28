import { useState, useEffect } from "react";

export default function CodebookManager({ onViewCodebook }) {
  const [codebooks, setCodebooks] = useState([]);
  const [renamingCb, setRenamingCb] = useState(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCodebooks();
  }, []);

  const fetchCodebooks = async () => {
    try {
      const response = await fetch("/api/list-codebooks");
      if (!response.ok) throw new Error("Failed to fetch codebooks");
      const data = await response.json();
      // ensure metadata fields exist for each codebook
      const enriched = (data.codebooks || []).map((cb) => ({
        ...cb,
        metadata: cb.metadata || {},
      }));
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

    try {
      const formData = new FormData();
      formData.append("old_id", oldId);
      formData.append("new_id", newName.trim());

      const response = await fetch("/api/rename-codebook/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Failed to rename codebook");

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
      const response = await fetch(`/api/delete-codebook/${cbId}`, {
        method: "DELETE",
      });

      if (!response.ok) throw new Error("Failed to delete codebook");

      fetchCodebooks();
    } catch (err) {
      console.error("Delete error:", err);
      setError(`Error deleting codebook: ${err.message}`);
    }
  };

  const startRename = (cbId) => {
    setRenamingCb(cbId);
    setNewName(cbId.toString());
  };

  const cancelRename = () => {
    setRenamingCb(null);
    setNewName("");
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
                      <button onClick={() => handleRenameCodebook(cb.id)}>
                        Save
                      </button>
                      <button onClick={cancelRename}>Cancel</button>
                    </div>
                  ) : (
                    <>
                      <div className="database-info">
                        <strong>{cb.name}</strong>
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
                          Rename
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
