import { useState, useEffect } from "react";
import { api } from "../../api";

const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper";
const actionBtn =
  "border border-paper px-3 py-1.5 text-sm transition-colors hover:bg-paper hover:text-ink";

export default function PromptManager({
  isOpen = true,
  onClose,
  onLoadPrompt,
  currentPrompt,
  promptType = "filter",
  examplePrompt = "",
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
          id: p.id,
          name:
            p.promptname ||
            p.display_name ||
            `Prompt ${Math.random().toString(36).slice(2, 6)}`,
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
    // Attempt to get authenticated user id for debugging and include it in POST
    let fetchedUserId = null;
    api
      .get("/api/me/")
      .then((meRes) => {
        const userId = meRes?.data?.id || meRes?.data?.sub || null;
        fetchedUserId = userId;
      })
      .catch((meErr) => {
        const uidMsg =
          meErr?.response?.data?.detail || meErr?.message || "unauthenticated";
        console.warn("Could not fetch /api/me:", uidMsg);
      })
      .finally(() => {
        const form = new FormData();
        form.append("promptname", promptName);
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
    if (editName !== null) form.append("promptname", editName);
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
    if (onClose) onClose();
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

  if (!isOpen) return null;

  const promptItems = [];
  if (examplePrompt && examplePrompt.trim()) {
    promptItems.push({
      id: "__example_prompt__",
      name: "Example prompt",
      prompt: examplePrompt,
      createdAt: null,
      isExample: true,
    });
  }
  promptItems.push(...savedPrompts.map((prompt) => ({ ...prompt, isExample: false })));

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-3xl overflow-y-auto border-2 border-paper bg-ink p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold">Saved Prompts</h3>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center text-lg transition-colors hover:bg-white/10"
            aria-label="Close prompt picker"
          >
            ×
          </button>
        </div>
        <div className="mt-5">
          {message && (
            <div
              className={`mb-4 flex items-center justify-between gap-3 border px-4 py-3 text-sm ${
                messageType === "error"
                  ? "border-error bg-error/10 text-error"
                  : "border-success bg-success/10 text-success"
              }`}
            >
              <span>{message}</span>
              <button
                type="button"
                onClick={clearMessage}
                className="text-lg leading-none hover:opacity-70"
                aria-label="Close message"
              >
                ×
              </button>
            </div>
          )}

          <div>
            {promptItems.length === 0 ? (
              <p className="py-6 text-center italic text-paper/70">No saved prompts yet.</p>
            ) : (
              <div className="flex flex-col gap-4">
                {promptItems.map((prompt) => (
                  <div
                    key={prompt.id}
                    className="flex items-start justify-between gap-4 border border-paper/20 p-4"
                  >
                    {!prompt.isExample && editingId === prompt.id ? (
                      <div className="flex flex-1 flex-col gap-3">
                        <div className="flex flex-col gap-1.5">
                          <label className="text-sm">Edit name</label>
                          <input
                            type="text"
                            className={inputClasses}
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                          />
                        </div>
                        <div className="flex flex-col gap-1.5">
                          <label className="text-sm">Edit prompt</label>
                          <textarea
                            className={`${inputClasses} resize-y`}
                            rows={4}
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => saveEdit(prompt.id)}
                            className={actionBtn}
                          >
                            Save
                          </button>
                          <button type="button" onClick={cancelEdit} className={actionBtn}>
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="min-w-0 flex-1">
                          <h4 className="font-semibold">{prompt.name}</h4>
                          <p className="mt-1.5 text-sm text-paper/70">
                            {prompt.prompt.length > 100
                              ? `${prompt.prompt.substring(0, 100)}...`
                              : prompt.prompt}
                          </p>
                          {prompt.isExample ? (
                            <small className="mt-1.5 block text-xs text-paper/50">Built-in</small>
                          ) : (
                            <small className="mt-1.5 block text-xs text-paper/50">
                              Saved: {new Date(prompt.createdAt).toLocaleDateString()}
                            </small>
                          )}
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <button
                            type="button"
                            onClick={() => loadPrompt(prompt)}
                            className={actionBtn}
                          >
                            Load
                          </button>
                          {!prompt.isExample && (
                            <>
                              <button
                                type="button"
                                onClick={() => startEdit(prompt)}
                                className={actionBtn}
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => deletePrompt(prompt.id)}
                                className="border border-error px-3 py-1.5 text-sm text-error transition-colors hover:bg-error hover:text-paper"
                              >
                                Delete
                              </button>
                            </>
                          )}
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
    </div>
  );
}
