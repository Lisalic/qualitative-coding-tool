import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";

export default function MarkdownView({
  selectedId,
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
        if (!resp.ok) throw new Error("Failed to fetch content");
        const data = await resp.json();
        const fetched = data.codebook ?? data.coded_data ?? "";
        setContent(fetched);
        setEditedContent(fetched);
        setNewName(selectedId);
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
      formData.append(saveIdFieldName, newName.trim());
      formData.append("content", editedContent || "");

      const res = await fetch(saveUrl, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Failed to save");

      if (onSaved) onSaved(newName.trim());
      else {
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
                setNewName(selectedId);
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
              {selectedId ? `${selectedId}` : emptyLabel}
            </h1>
            {selectedId && (
              <button
                onClick={() => {
                  setIsEditing(true);
                  setEditedContent(content);
                  setNewName(selectedId);
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
