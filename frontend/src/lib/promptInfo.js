/** True when there is any provenance worth showing a "Show Prompt" button
 * for -- shared by CodebookWorkspaceSection.jsx and
 * CodingWorkspaceSection.jsx, both of which render PromptPanel.
 */
export function hasPromptInfo({ systemPrompt, instructions, promptMeta }) {
  return Boolean(systemPrompt || instructions || promptMeta);
}
