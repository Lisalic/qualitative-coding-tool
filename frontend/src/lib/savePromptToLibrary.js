import { api } from "../api";

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

  let fetchedUserId = null;
  try {
    const me = await api.get("/api/me/");
    fetchedUserId = me?.data?.id || me?.data?.sub || null;
  } catch (e) {
    console.warn("Could not fetch /api/me", e);
  }

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
  if (fetchedUserId) form.append("user_id", fetchedUserId);

  const res = await api.post("/api/prompts/", form);
  const saved = res && res.data ? res.data : null;
  const label =
    (saved &&
      (saved.promptname || saved.display_name || saved.prompt)) ||
    "Prompt saved";
  return { label };
}
