import { useState, useEffect } from "react";
import "../styles/Home.css";
import { api } from "../api";

export default function PromptManager({
  onLoadPrompt,
  currentPrompt,
  promptType = "filter",
}) {
  const [savedPrompts, setSavedPrompts] = useState([]);
  const [newPromptContent, setNewPromptContent] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");
  const [editContent, setEditContent] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");
  useEffect(() => {
    loadSavedPrompts();
  }, []);

  useEffect(() => {
    const handler = () => {
      loadSavedPrompts();
    };
    try {
      window.addEventListener("promptSaved", handler);
    } catch (e) {}
    return () => {
      try {
        window.removeEventListener("promptSaved", handler);
      } catch (e) {}
    };
  }, []);

  const showMessage = (text, type = "success") => {
    setMessage(text);
    setMessageType(type);
  };

  const clearMessage = () => {
    setMessage("");
    setMessageType("");
  };

  const loadSavedPrompts = () => {
    api
      .get(`/api/prompts/?prompt_type=${encodeURIComponent(promptType)}`)
      .then((res) => {
        const prompts = (res.data && res.data.prompts) || [];
        const mapped = prompts.map((p) => ({
          id: p.rowid,
          name: p.display_name,
          prompt: p.prompt,
          createdAt: new Date().toISOString(),
        }));
        setSavedPrompts(mapped);
      })
      .catch((err) => {
        setSavedPrompts([]);
        const msg =
          err?.response?.data?.detail ||
          err?.response?.data ||
          err?.message ||
          "Failed to load prompts";
        // do not show error as a blocking message on load, but log for debugging
        console.warn("Failed to load prompts:", msg);
      });
  };

  const savePrompt = () => {
    if (!newPromptContent.trim()) {
      showMessage("Please enter prompt content", "error");
      return;
    }
    const nextNumber = savedPrompts.length + 1;
    const promptName = `Prompt ${nextNumber}`;

    // Log the row that will be created for debugging and fetch user id
    const debugRow = {
      display_name: promptName,
      prompt: newPromptContent.trim(),
      type: "filter",
    };
    // Attempt to get authenticated user id for debugging and include it in POST
    let fetchedUserId = null;
    api
      .get("/api/me")
      .then((meRes) => {
        const userId = meRes?.data?.id || meRes?.data?.sub || null;
        fetchedUserId = userId;
        console.log("Creating prompt row (with user):", {
          ...debugRow,
          userId,
        });
      })
      .catch((meErr) => {
        const uidMsg =
          meErr?.response?.data?.detail || meErr?.message || "unauthenticated";
        console.warn("Could not fetch /api/me:", uidMsg);
        console.log("Creating prompt row:", debugRow);
      })
      .finally(() => {
        const form = new FormData();
        form.append("display_name", promptName);
        form.append("prompt", newPromptContent.trim());
        form.append("type", promptType);
        if (fetchedUserId) form.append("user_id", fetchedUserId);

        api
          .post("/api/prompts/", form)
          .then((res) => {
            const p = res.data || {};
            // reload prompts for current page type
            loadSavedPrompts();
            setNewPromptContent("");
            showMessage("Prompt saved successfully!");
          })
          .catch((err) => {
            const msg =
              err?.response?.data?.detail ||
              err?.response?.data ||
              err?.message ||
              "Failed to save prompt";
            showMessage(String(msg), "error");
          });
      });
  };

  const startEdit = (prompt) => {
    setEditingId(prompt.id);
    setEditName(prompt.name || "");
    setEditContent(prompt.prompt || "");
    clearMessage();
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName("");
    setEditContent("");
  };

  const saveEdit = (id) => {
    if (!editContent.trim()) {
      showMessage("Please enter prompt content", "error");
      return;
    }
    const form = new FormData();
    if (editName !== null) form.append("display_name", editName);
    form.append("prompt", editContent.trim());
    form.append("type", promptType);

    api
      .post(`/api/prompts/${id}/update`, form)
      .then((res) => {
        // refresh list after update
        loadSavedPrompts();
        setEditingId(null);
        setEditName("");
        setEditContent("");
        showMessage("Prompt updated successfully!");
      })
      .catch((err) => {
        const msg =
          err?.response?.data?.detail ||
          err?.response?.data ||
          err?.message ||
          "Failed to update prompt";
        showMessage(String(msg), "error");
      });
  };

  const loadPrompt = (prompt) => {
    onLoadPrompt(prompt.prompt);
  };

  const deletePrompt = (id) => {
    api
      .delete(`/api/prompts/${id}`)
      .then(() => {
        // refresh list after delete
        loadSavedPrompts();
        showMessage("Prompt deleted successfully!");
      })
      .catch((err) => {
        const msg =
          err?.response?.data?.detail ||
          err?.response?.data ||
          err?.message ||
          "Failed to delete prompt";
        showMessage(String(msg), "error");
      });
  };

  return (
    <div className="prompt-manager">
      <div className="prompt-manager-content">
        {message && (
          <div className={`prompt-message ${messageType}`}>
            <span>{message}</span>
            <button
              type="button"
              onClick={clearMessage}
              className="message-close-btn"
              aria-label="Close message"
            >
              ×
            </button>
          </div>
        )}

        <div>
          <h3 style={{ textAlign: "center" }}>Saved Prompts</h3>
          {savedPrompts.length === 0 ? (
            <p className="no-prompts">No saved prompts yet.</p>
          ) : (
            <div className="prompts-list">
              {savedPrompts.map((prompt) => (
                <div key={prompt.id} className="prompt-item">
                  {editingId === prompt.id ? (
                    <div className="prompt-edit">
                      <div className="form-group">
                        <label>Edit name</label>
                        <input
                          type="text"
                          className="form-input"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                        />
                      </div>
                      <div className="form-group">
                        <label>Edit prompt</label>
                        <textarea
                          className="form-input"
                          rows={4}
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                        />
                      </div>
                      <div className="prompt-actions">
                        <button
                          type="button"
                          onClick={() => saveEdit(prompt.id)}
                          className="save-prompt-btn"
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={cancelEdit}
                          className="delete-prompt-btn"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="prompt-info">
                        <h4>{prompt.name}</h4>
                        <p className="prompt-preview">
                          {prompt.prompt.length > 100
                            ? `${prompt.prompt.substring(0, 100)}...`
                            : prompt.prompt}
                        </p>
                        <small className="prompt-date">
                          Saved:{" "}
                          {new Date(prompt.createdAt).toLocaleDateString()}
                        </small>
                      </div>
                      <div className="prompt-actions">
                        <button
                          type="button"
                          onClick={() => loadPrompt(prompt)}
                          className="load-prompt-btn"
                        >
                          Load
                        </button>
                        <button
                          type="button"
                          onClick={() => startEdit(prompt)}
                          className="load-prompt-btn"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => deletePrompt(prompt.id)}
                          className="delete-prompt-btn"
                        >
                          Delete
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
