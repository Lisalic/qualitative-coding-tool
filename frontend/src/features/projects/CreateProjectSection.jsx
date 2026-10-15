import { btn, btnPrimary, input } from "../../lib/uiClasses";

const inputClasses = `${input} py-2.5`;

export default function CreateProjectSection({
  showForm,
  name,
  description,
  message,
  messageIsError,
  creating,
  onCreateClick,
  onNameChange,
  onDescriptionChange,
  onSubmit,
  onCancel,
}) {
  if (!showForm) {
    return (
      <div className="mt-6 flex justify-center">
        <button
          type="button"
          className={btnPrimary}
          onClick={onCreateClick}
        >
          Create new project
        </button>
      </div>
    );
  }


  return (
    <div className="border border-line bg-surface p-3">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide">Create new project</h2>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="newProjectName" className="text-sm">
            Project name
          </label>
          <input
            id="newProjectName"
            autoFocus
            required
            className={inputClasses}
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder="Enter project name"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="newProjectDescription" className="text-sm">
            Description (optional)
          </label>
          <textarea
            id="newProjectDescription"
            className={`${inputClasses} min-h-[100px] resize-y`}
            value={description}
            onChange={(event) => onDescriptionChange(event.target.value)}
            placeholder="What this project is about…"
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className={btnPrimary}
            disabled={creating}
          >
            {creating ? "Creating…" : "Create project"}
          </button>
          <button type="button" className={btn} onClick={onCancel}>
            Cancel
          </button>
        </div>
        {message && (
          <div
            role={messageIsError ? "alert" : "status"}
            className={`border px-4 py-3 text-sm ${
              messageIsError
                ? "border-error bg-error/10 text-error"
                : "border-success bg-success/10 text-success"
            }`}
          >
            {message}
          </div>
        )}
      </form>
    </div>
  );
}
