import { useCallback, useState, useEffect } from "react";
import { api } from "../../api";
import DialogService from "../feedback/DialogService";
import { useModalBehavior } from "../feedback/useModalBehavior";
import { btn, btnDanger, input, textarea } from "../../lib/uiClasses";

const inputClasses = input;
const actionBtn = btn;

/** A readable message from an axios error -- never "[object Object]". */
function errorText(err, fallback) {
  const data = err?.response?.data;
  const detail = data?.detail ?? data?.error ?? data;
  return typeof detail === "string" && detail.trim() ? detail : fallback;
}

export default function PromptManager({
  isOpen = true,
  onClose,
  onLoadPrompt,
  promptType = "filter",
  examplePrompt = "",
}) {
  const [savedPrompts, setSavedPrompts] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");
  const [editContent, setEditContent] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");

  const loadSavedPrompts = useCallback(() => {
    api
      .get(`/api/prompts/?prompt_type=${encodeURIComponent(promptType)}`)
      .then((res) => {
        const prompts = (res.data && res.data.prompts) || [];
        const mapped = prompts.map((p) => ({
          id: p.id,
          name: p.promptname || p.display_name || `Prompt ${p.id}`,
          prompt: p.prompt,
        }));
        setSavedPrompts(mapped);
      })
      .catch((err) => {
        setSavedPrompts([]);
        console.warn("Failed to load prompts:", err);
        setMessage(errorText(err, "Couldn't load your saved prompts. Close this and try again."));
        setMessageType("error");
      });
  }, [promptType]);

  useEffect(() => {
    loadSavedPrompts();
  }, [loadSavedPrompts]);

  useEffect(() => {
    window.addEventListener("promptSaved", loadSavedPrompts);
    return () => window.removeEventListener("promptSaved", loadSavedPrompts);
  }, [loadSavedPrompts]);

  const showMessage = (text, type = "success") => {
    setMessage(text);
    setMessageType(type);
  };

  const clearMessage = () => {
    setMessage("");
    setMessageType("");
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
    if (editName !== null && !editName.trim()) {
      showMessage("Please enter a prompt name", "error");
      return;
    }
    const form = new FormData();
    if (editName !== null) form.append("promptname", editName.trim());
    form.append("prompt", editContent.trim());
    form.append("type", promptType);

    api
      .post(`/api/prompts/${id}/update`, form)
      .then(() => {
        loadSavedPrompts();
        setEditingId(null);
        setEditName("");
        setEditContent("");
        showMessage("Prompt updated.");
      })
      .catch((err) => {
        showMessage(errorText(err, "Couldn't update the prompt. Please try again."), "error");
      });
  };

  const loadPrompt = (prompt) => {
    onLoadPrompt(prompt.prompt);
    if (onClose) onClose();
  };

  const deletePrompt = async (prompt) => {
    const confirmed = await DialogService.confirm(
      `Delete the saved prompt "${prompt.name}"? This cannot be undone.`,
      { title: "Delete prompt", confirmLabel: "Delete", danger: true },
    );
    if (!confirmed) return;
    const { id } = prompt;
    api
      .delete(`/api/prompts/${id}`)
      .then(() => {
        loadSavedPrompts();
        showMessage("Prompt deleted.");
      })
      .catch((err) => {
        showMessage(errorText(err, "Couldn't delete the prompt. Please try again."), "error");
      });
  };

  return isOpen ? (
    <PromptManagerDialog
      onClose={onClose}
      examplePrompt={examplePrompt}
      savedPrompts={savedPrompts}
      message={message}
      messageType={messageType}
      clearMessage={clearMessage}
      editingId={editingId}
      editName={editName}
      setEditName={setEditName}
      editContent={editContent}
      setEditContent={setEditContent}
      saveEdit={saveEdit}
      cancelEdit={cancelEdit}
      startEdit={startEdit}
      loadPrompt={loadPrompt}
      deletePrompt={deletePrompt}
    />
  ) : null;
}

/** The open dialog -- its own component so Escape/focus handling mounts
 * and unmounts with it. */
function PromptManagerDialog({
  onClose,
  examplePrompt,
  savedPrompts,
  message,
  messageType,
  clearMessage,
  editingId,
  editName,
  setEditName,
  editContent,
  setEditContent,
  saveEdit,
  cancelEdit,
  startEdit,
  loadPrompt,
  deletePrompt,
}) {
  const dialogRef = useModalBehavior(onClose);

  const promptItems = [];
  if (examplePrompt && examplePrompt.trim()) {
    promptItems.push({
      id: "__example_prompt__",
      name: "Example prompt",
      prompt: examplePrompt,
      isExample: true,
    });
  }
  promptItems.push(...savedPrompts.map((prompt) => ({ ...prompt, isExample: false })));

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="promptManagerTitle"
        className="max-h-[90vh] w-full max-w-3xl overflow-y-auto border-2 border-paper bg-ink p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3">
          <h3 id="promptManagerTitle" className="text-lg font-semibold">
            Saved prompts
          </h3>
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
              role={messageType === "error" ? "alert" : "status"}
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
                    className="flex items-start justify-between gap-4 border border-line p-4"
                  >
                    {!prompt.isExample && editingId === prompt.id ? (
                      <div className="flex flex-1 flex-col gap-3">
                        <div className="flex flex-col gap-1.5">
                          <label htmlFor={`promptName-${prompt.id}`} className="text-sm">
                            Name
                          </label>
                          <input
                            id={`promptName-${prompt.id}`}
                            type="text"
                            className={inputClasses}
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                          />
                        </div>
                        <div className="flex flex-col gap-1.5">
                          <label htmlFor={`promptText-${prompt.id}`} className="text-sm">
                            Prompt
                          </label>
                          <textarea
                            id={`promptText-${prompt.id}`}
                            className={textarea}
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
                              ? `${prompt.prompt.substring(0, 100)}…`
                              : prompt.prompt}
                          </p>
                          {prompt.isExample ? (
                            <small className="mt-1.5 block text-xs text-paper/50">Built-in</small>
                          ) : null}
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
                                onClick={() => deletePrompt(prompt)}
                                className={btnDanger}
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
