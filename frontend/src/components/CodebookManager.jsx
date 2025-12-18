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
      setCodebooks(data.codebooks);
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

  return (
    <div>
      {codebooks.length > 0 && (
        <div className="database-section">
          <div className="database-selection">
            <h2>Manage Codebooks</h2>
            <p>Manage your generated codebooks:</p>
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
                      <span>{cb.name}</span>
                      <div className="database-actions">
                        <button
                          onClick={() => onViewCodebook(cb.id)}
                          className="btn"
                        >
                          View
                        </button>
                        <button
                          onClick={() => startRename(cb.id)}
                          className="btn btn-secondary btn-small"
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
                          className="btn btn-danger btn-small"
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
