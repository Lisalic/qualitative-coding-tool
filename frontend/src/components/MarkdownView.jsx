import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";

export default function MarkdownView({
  selectedId,
  title,
  // If true, this save targets a Postgres project and will send schema_name instead
  saveAsProject = false,
  projectSchema = null,
  fetchStyle = "query",
  fetchBase = "/api/codebook",
  queryParamName = "codebook_id",
  saveUrl = "/api/save-codebook/",
  saveIdFieldName = "codebook_id",
  onSaved = null,
  emptyLabel = "No item selected",
}) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [newName, setNewName] = useState("");

  useEffect(() => {
    if (!selectedId) {
      setContent("");
      setEditedContent("");
      setNewName("");
      setLoading(false);
      return;
    }

    const fetchContent = async () => {
      setLoading(true);
      setError(null);
      try {
        let url;
        if (fetchStyle === "query") {
          const sep = fetchBase.includes("?") ? "&" : "?";
          url = `${fetchBase}${sep}${queryParamName}=${encodeURIComponent(
            selectedId
          )}`;
        } else {
          url = `${fetchBase}/${encodeURIComponent(selectedId)}`;
        }
        const resp = await fetch(url);
        if (!resp.ok) {
          // try parse server error message
          try {
            const err = await resp.json();
            const msg = err.error || err.message || JSON.stringify(err);
            throw new Error(msg || "Failed to fetch content");
          } catch (e) {
            throw new Error("Failed to fetch content");
          }
        }
        const data = await resp.json();
        const fetched = data.codebook ?? data.coded_data ?? "";
        setContent(fetched);
        setEditedContent(fetched);
        setNewName(title || selectedId);
      } catch (err) {
        console.error("Fetch content error:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchContent();
  }, [selectedId, fetchBase, fetchStyle, queryParamName]);

  const handleSave = async () => {
    if (!newName.trim()) {
      setError("Name cannot be empty");
      return;
    }

    try {
      const formData = new FormData();
      if (saveAsProject && projectSchema) {
        // For project-backed codebooks, send the schema identifier and include optional display_name
        formData.append(saveIdFieldName, projectSchema);
        formData.append("display_name", newName.trim());
      } else {
        formData.append(saveIdFieldName, newName.trim());
      }
      formData.append("content", editedContent || "");

      const fetchOpts = { method: "POST", body: formData };
      if (saveAsProject) fetchOpts.credentials = "include";
      const res = await fetch(saveUrl, fetchOpts);
      if (!res.ok) {
        let errText = "Failed to save";
        try {
          const j = await res.json();
          errText = j.error || j.message || errText;
        } catch (e) {}
        throw new Error(errText);
      }

      // Parse response JSON and call onSaved with either returned object or new name
      let respJson = null;
      try {
        respJson = await res.json();
      } catch (e) {
        respJson = null;
      }

      if (onSaved) {
        if (saveAsProject && respJson) onSaved(respJson);
        else onSaved(newName.trim());
      } else {
        setContent(editedContent);
      }
      setIsEditing(false);
      setError(null);
    } catch (err) {
      console.error("Save error:", err);
      setError(`Error saving content: ${err.message}`);
    }
  };

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          gap: "20px",
          marginBottom: "20px",
        }}
      >
        {isEditing ? (
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <label style={{ color: "#ffffff" }}>Name:</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              style={{
                padding: "5px 10px",
                border: "1px solid #ffffff",
                borderRadius: "4px",
                backgroundColor: "#000000",
                color: "#ffffff",
              }}
            />
            <button
              onClick={handleSave}
              className="view-button"
              style={{ fontSize: "14px", padding: "5px 10px" }}
            >
              Save
            </button>
            <button
              onClick={() => {
                setIsEditing(false);
                setEditedContent(content);
                setNewName(title || selectedId);
                setError(null);
              }}
              className="view-button"
              style={{
                fontSize: "14px",
                padding: "5px 10px",
                backgroundColor: "#666",
              }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <>
            <h1 style={{ color: "#ffffff", margin: 0 }}>
              {title || (selectedId ? `${selectedId}` : emptyLabel)}
            </h1>
            {selectedId && (
              <button
                onClick={() => {
                  setIsEditing(true);
                  setEditedContent(content);
                  setNewName(title || selectedId);
                }}
                className="view-button"
                style={{ fontSize: "14px", padding: "8px 16px" }}
              >
                Edit
              </button>
            )}
          </>
        )}
      </div>

      {loading && <p style={{ color: "#ffffff" }}>Loading...</p>}
      {error && <p className="error-message">{error}</p>}

      <div
        style={{
          backgroundColor: "#000000",
          border: "1px solid #ffffff",
          borderRadius: "4px",
          padding: "20px",
          color: "#ffffff",
        }}
      >
        {isEditing ? (
          <textarea
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            rows={40}
            style={{
              width: "100%",
              padding: "8px",
              border: "1px solid #ffffff",
              borderRadius: "4px",
              backgroundColor: "#000000",
              color: "#ffffff",
              fontFamily: "monospace",
              resize: "vertical",
            }}
            placeholder="Enter content..."
          />
        ) : (
          <ReactMarkdown
            components={{
              h3: ({ children }) => (
                <h3 style={{ color: "#ffffff", marginTop: "20px" }}>
                  {children}
                </h3>
              ),
              h4: ({ children }) => (
                <h4 style={{ color: "#ffffff", marginTop: "15px" }}>
                  {children}
                </h4>
              ),
              ul: ({ children }) => (
                <ul style={{ color: "#ffffff" }}>{children}</ul>
              ),
              li: ({ children }) => (
                <li style={{ color: "#ffffff" }}>{children}</li>
              ),
              strong: ({ children }) => (
                <strong style={{ color: "#ffffff" }}>{children}</strong>
              ),
              p: ({ children }) => (
                <p style={{ color: "#ffffff" }}>{children}</p>
              ),
            }}
          >
            {content}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}
