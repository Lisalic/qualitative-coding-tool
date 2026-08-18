const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper";

export default function CreateProjectSection({
  showForm,
  name,
  description,
  message,
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
          className="border-2 border-paper px-6 py-3 text-base font-semibold transition-colors hover:bg-paper hover:text-ink"
          onClick={onCreateClick}
          aria-label="Create New Project"
        >
          Create New Project
        </button>
      </div>
    );
  }

  const isError = message.toLowerCase().includes("error");

  return (
    <div className="mt-6 border-2 border-paper p-6">
      <h2 className="mb-4 text-xl font-semibold">Create New Project</h2>
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm">Project Name *</label>
          <input
            className={inputClasses}
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder="Enter project name"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm">Description</label>
          <textarea
            className={`${inputClasses} min-h-[100px] resize-y`}
            value={description}
            onChange={(event) => onDescriptionChange(event.target.value)}
            placeholder="Enter project description (optional)"
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            className="border-2 border-paper px-6 py-3 text-base font-semibold transition-colors hover:bg-paper hover:text-ink"
          >
            Create Project
          </button>
          <button
            type="button"
            className="border border-paper px-6 py-3 text-base transition-colors hover:bg-paper hover:text-ink"
            onClick={onCancel}
          >
            Cancel
          </button>
        </div>
        {message && (
          <div
            className={`border px-4 py-3 text-sm ${
              isError
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
