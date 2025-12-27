import { useState, useEffect } from "react";
import "../styles/Home.css";

export default function PromptManager({ onLoadPrompt, currentPrompt }) {
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

  const showMessage = (text, type = "success") => {
    setMessage(text);
    setMessageType(type);
  };

  const clearMessage = () => {
    setMessage("");
    setMessageType("");
  };

  const loadSavedPrompts = () => {
    const prompts = JSON.parse(
      localStorage.getItem("savedFilterPrompts") || "[]"
    );
    setSavedPrompts(prompts);
  };

  const savePrompt = () => {
    if (!newPromptContent.trim()) {
      showMessage("Please enter prompt content", "error");
      return;
    }

    const nextNumber = savedPrompts.length + 1;
    const promptName = `Prompt ${nextNumber}`;

    const newPrompt = {
      id: Date.now(),
      name: promptName,
      prompt: newPromptContent.trim(),
      createdAt: new Date().toISOString(),
    };

    const updatedPrompts = [...savedPrompts, newPrompt];
    setSavedPrompts(updatedPrompts);
    localStorage.setItem("savedFilterPrompts", JSON.stringify(updatedPrompts));

    setNewPromptContent("");
    showMessage("Prompt saved successfully!");
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
    const updated = savedPrompts.map((p) => {
      if (p.id === id) {
        return {
          ...p,
          name: editName || p.name,
          prompt: editContent.trim(),
        };
      }
      return p;
    });
    setSavedPrompts(updated);
    localStorage.setItem("savedFilterPrompts", JSON.stringify(updated));
    setEditingId(null);
    setEditName("");
    setEditContent("");
    showMessage("Prompt updated successfully!");
  };

  const loadPrompt = (prompt) => {
    onLoadPrompt(prompt.prompt);
  };

  const deletePrompt = (id) => {
    const updatedPrompts = savedPrompts.filter((p) => p.id !== id);
    setSavedPrompts(updatedPrompts);
    localStorage.setItem("savedFilterPrompts", JSON.stringify(updatedPrompts));
    showMessage("Prompt deleted successfully!");
  };

  return (
    <div className="prompt-manager">
      <h1
        style={{
          textAlign: "center",
          fontSize: "28px",
          fontWeight: "600",
          margin: "0 0 30px 0",
        }}
      >
        Saved Prompts
      </h1>
      <div className="prompt-manager-content">
        <div className="save-prompt-section">
          <h3>Save New Prompt</h3>
          <div className="form-group">
            <textarea
              value={newPromptContent}
              onChange={(e) => setNewPromptContent(e.target.value)}
              placeholder="Enter your prompt content here..."
              className="form-input"
              rows={4}
            />
            <button
              type="button"
              onClick={savePrompt}
              className="save-prompt-btn"
              disabled={!newPromptContent.trim()}
            >
              Save Prompt
            </button>
          </div>
        </div>

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
          <h3>Saved Prompts</h3>
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
