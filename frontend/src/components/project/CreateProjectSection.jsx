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
      <div className="layout-center mt-md">
        <button
          className="btn btn-primary btn-large"
          onClick={onCreateClick}
          aria-label="Create New Project"
        >
          Create New Project
        </button>
      </div>
    );
  }

  return (
    <div className="panel mt-md layout-card--padded">
      <h2 className="heading-md">Create New Project</h2>
      <form onSubmit={onSubmit}>
        <div className="form__group">
          <label className="form__label">Project Name *</label>
          <input
            className="form__input"
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            placeholder="Enter project name"
          />
        </div>
        <div className="form__group">
          <label className="form__label">Description</label>
          <textarea
            className="form__textarea"
            value={description}
            onChange={(event) => onDescriptionChange(event.target.value)}
            placeholder="Enter project description (optional)"
          />
        </div>
        <div className="form__actions">
          <button type="submit" className="btn btn-primary btn-large">
            Create Project
          </button>
          <button type="button" className="btn btn-secondary btn-large" onClick={onCancel}>
            Cancel
          </button>
        </div>
        {message && (
          <div className={`alert ${message.includes("Error") ? "alert--error" : "alert--success"}`}>
            {message}
          </div>
        )}
      </form>
    </div>
  );
}
