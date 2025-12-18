import { useState, useEffect } from "react";
import "../styles/Home.css";

export default function PromptManager({ onLoadPrompt, currentPrompt }) {
  const [savedPrompts, setSavedPrompts] = useState([]);
  const [newPromptContent, setNewPromptContent] = useState("");
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
              className="btn btn-primary"
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
              className="btn btn-small"
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
                  <div className="prompt-info">
                    <h4>{prompt.name}</h4>
                    <p className="prompt-preview">
                      {prompt.prompt.length > 100
                        ? `${prompt.prompt.substring(0, 100)}...`
                        : prompt.prompt}
                    </p>
                    <small className="prompt-date">
                      Saved: {new Date(prompt.createdAt).toLocaleDateString()}
                    </small>
                  </div>
                  <div className="prompt-actions">
                    <button
                      type="button"
                      onClick={() => loadPrompt(prompt)}
                      className="btn btn-secondary btn-small"
                    >
                      Load
                    </button>
                    <button
                      type="button"
                      onClick={() => deletePrompt(prompt.id)}
                      className="btn btn-danger btn-small"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
