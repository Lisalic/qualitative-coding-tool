import { api } from "../api/client";

/**
 * Saves the current prompt text to the user's prompt library.
 * @param {"generate"|"apply"|"filter"} promptType
 * @param {string} promptText
 * @returns {Promise<{ label: string }>}
 */
export async function savePromptToLibrary(promptType, promptText) {
  const trimmed = (promptText || "").trim();
  if (!trimmed) {
    throw new Error("EMPTY_PROMPT");
  }

  // No `/api/me/` round trip: the server takes the owner from the session
  // (`prompt_routes.create_prompt`) and ignores any `user_id` field.
  let promptName = `Prompt ${Date.now()}`;
  try {
    const listRes = await api.get(
      `/api/prompts/?prompt_type=${encodeURIComponent(promptType)}`,
    );
    const prompts = (listRes.data && listRes.data.prompts) || [];
    promptName = `Prompt ${prompts.length + 1}`;
  } catch {
    // fallback to timestamp-based name
  }

  const form = new FormData();
  form.append("promptname", promptName);
  form.append("prompt", trimmed);
  form.append("type", promptType);

  const res = await api.post("/api/prompts/", form);
  const saved = res && res.data ? res.data : null;
  const label =
    (saved &&
      (saved.promptname || saved.display_name || saved.prompt)) ||
    "Prompt saved";
  return { label };
}
