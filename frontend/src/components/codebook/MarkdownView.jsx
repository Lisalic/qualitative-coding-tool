import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../../api";
import ReactMarkdown from "react-markdown";

const btnClasses =
  "border border-paper px-4 py-2 text-sm transition-colors hover:bg-paper hover:text-ink";
const inputClasses =
  "border border-paper bg-white/5 px-2.5 py-1.5 text-paper focus:outline-none focus:ring-2 focus:ring-paper";

export default function MarkdownView({
  selectedId,
  title,
  description,
  // If true, this save targets a Postgres project and will send schema_name instead
  saveAsProject = false,
  projectSchema = null,
  fetchStyle = "query",
  fetchBase = "/api/codebook",
  queryParamName = "codebook_id",
  saveUrl = "/api/save-file-codebook/",
  saveIdFieldName = "schema_name",
  onSaved = null,
  emptyLabel = "No item selected",
  systemPrompt = "",
  userPrompt = "",
  comparePath = "/compare-coding",
  compareStateKey = "codingA",
}) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [newName, setNewName] = useState("");
  const [showSystemPrompt, setShowSystemPrompt] = useState(false);
  const [showUserPrompt, setShowUserPrompt] = useState(false);
  const navigate = useNavigate();

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
            selectedId,
          )}`;
        } else {
          url = `${fetchBase}/${encodeURIComponent(selectedId)}`;
        }
        const resp = await apiFetch(url);
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
      const res = await apiFetch(saveUrl, fetchOpts);
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
      <div className="mb-5 flex items-center justify-center gap-5">
        {isEditing ? (
          <div className="flex items-center gap-2.5">
            <label>Name:</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className={inputClasses}
            />
            <button type="button" onClick={handleSave} className={btnClasses}>
              Save
            </button>
            <button
              type="button"
              onClick={() => {
                setIsEditing(false);
                setEditedContent(content);
                setNewName(title || selectedId);
                setError(null);
              }}
              className={btnClasses}
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex w-full items-start gap-2">
            <div className="flex-1" />
            <div className="flex flex-col items-center gap-2 text-center">
              <h1 className="text-2xl font-bold">
                {title || (selectedId ? `${selectedId}` : emptyLabel)}
              </h1>
              {description ? (
                <div className="text-sm text-paper/70">{description}</div>
              ) : null}
            </div>
            <div className="flex flex-1 flex-col items-end justify-end gap-2">
              {selectedId && (
                <>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        navigate(comparePath, {
                          state: { [compareStateKey]: selectedId },
                        });
                      }}
                      className={btnClasses}
                    >
                      Compare
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setIsEditing(true);
                        setEditedContent(content);
                        setNewName(title || selectedId);
                      }}
                      className={btnClasses}
                    >
                      Edit
                    </button>
                  </div>
                  {systemPrompt && (
                    <button
                      type="button"
                      onClick={() => setShowSystemPrompt(!showSystemPrompt)}
                      className={btnClasses}
                    >
                      {showSystemPrompt ? "Hide" : "Show"} System Prompt
                    </button>
                  )}
                  {userPrompt && (
                    <button
                      type="button"
                      onClick={() => setShowUserPrompt(!showUserPrompt)}
                      className={btnClasses}
                    >
                      {showUserPrompt ? "Hide" : "Show"} User Prompt
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {(showSystemPrompt || showUserPrompt) && (
        <div className="mt-5 flex w-full justify-start">
          <div className="w-full max-w-[800px]">
            {showSystemPrompt && (
              <div className="mt-1.5 max-h-[200px] max-w-[800px] overflow-y-auto whitespace-pre-wrap border border-paper/20 bg-white/5 p-2.5 font-mono text-paper/80">
                {systemPrompt}
              </div>
            )}
            {showUserPrompt && (
              <div className="mt-1.5 max-h-[200px] max-w-[800px] overflow-y-auto whitespace-pre-wrap border border-paper/20 bg-white/5 p-2.5 font-mono text-paper/80">
                {userPrompt}
              </div>
            )}
          </div>
        </div>
      )}

      {loading && <p className="text-paper/70">Loading...</p>}
      {error && (
        <p className="mt-4 border border-error bg-error/10 px-4 py-3 text-sm text-error">
          {error}
        </p>
      )}

      <div className="border border-paper p-5">
        {isEditing ? (
          <textarea
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            rows={40}
            className="w-full resize-y border border-paper bg-white/5 p-2 font-mono text-paper focus:outline-none focus:ring-2 focus:ring-paper"
            placeholder="Enter content..."
          />
        ) : (
          <ReactMarkdown>{content}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
