import { useMemo } from "react";
import Dropdown from "../primitives/Dropdown";
import { input, select, textarea } from "../../lib/uiClasses";
import { toProjectOptions } from "../../lib/projectOptions";

/**
 * Name / description / project trio that names the artifact an editor's
 * session will become -- identical across Filter, Codebook and Apply
 * Codebook, written three times before this
 * (`FilterDecisionsRail.jsx`, `CodebookCodesRail.jsx`,
 * `CodingSetupPanel.jsx`).
 *
 * The project is required -- every artifact belongs to one -- so the
 * blank option is a prompt, not a "no project" choice; each editor's
 * submit gate checks it alongside the name.
 *
 * `projectOptions` takes raw project rows (`{ id, projectname }`, what
 * `useToolPanelData` already returns) rather than a pre-mapped
 * `{value,label}` shape, so a caller never needs its own mapping step.
 */
export default function EditorOutputFields({
  idPrefix,
  name,
  onNameChange,
  namePlaceholder = "",
  nameLabel = "Name",
  description,
  onDescriptionChange,
  selectedProject,
  onProjectChange,
  projectOptions,
  disabled,
}) {
  const projectChoices = useMemo(() => toProjectOptions(projectOptions), [projectOptions]);

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${idPrefix}Name`} className="text-sm">
          {nameLabel}
        </label>
        <input
          id={`${idPrefix}Name`}
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder={namePlaceholder}
          className={input}
          disabled={disabled}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${idPrefix}Description`} className="text-sm">
          Description (optional)
        </label>
        <textarea
          id={`${idPrefix}Description`}
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          placeholder="Optional description"
          rows={2}
          className={textarea}
          disabled={disabled}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${idPrefix}Project`} className="text-sm">
          Project
        </label>
        <Dropdown
          id={`${idPrefix}Project`}
          value={selectedProject || ""}
          options={projectChoices}
          onChange={onProjectChange}
          placeholder="Select a project"
          disabled={disabled}
          triggerClassName={`w-full ${select}`}
          listLabel="Project"
          searchPlaceholder="Search projects…"
          emptyMessage="No projects match that search."
        />
      </div>
    </>
  );
}
