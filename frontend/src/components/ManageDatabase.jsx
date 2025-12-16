export default function ManageDatabase({
  databases,
  selectedDatabases,
  onSelect,
  onCreateMaster,
  loading,
  successMessage,
  renamingDb,
  newName,
  onNewNameChange,
  onRename,
  onStartRename,
  onCancelRename,
  onDelete,
}) {
  return (
    <div className="database-section">
      <div className="database-selection">
        <h2>Manage Databases</h2>
        <p>Select databases to combine into the master database:</p>
        <div className="database-list">
          {databases.map((dbName) => (
            <div key={dbName} className="database-item">
              {renamingDb === dbName ? (
                <div className="rename-controls">
                  <input
                    type="text"
                    value={newName}
                    onChange={(e) => onNewNameChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") onRename(dbName);
                      if (e.key === "Escape") onCancelRename();
                    }}
                    autoFocus
                  />
                  <button onClick={() => onRename(dbName)}>Save</button>
                  <button onClick={onCancelRename}>Cancel</button>
                </div>
              ) : (
                <>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedDatabases.includes(dbName)}
                      onChange={() => onSelect(dbName)}
                    />
                    {dbName.replace(".db", "")}
                  </label>
                  <div className="database-actions">
                    <button
                      onClick={() => onStartRename(dbName)}
                      className="rename-btn"
                    >
                      Rename
                    </button>
                    <button
                      onClick={() => onDelete(dbName)}
                      className="delete-btn"
                    >
                      Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>

        <button
          onClick={onCreateMaster}
          disabled={selectedDatabases.length === 0 || loading}
          className="merge-btn"
        >
          {loading ? "Creating..." : "Create Master Database"}
        </button>

        {successMessage && (
          <div className="success-message">{successMessage}</div>
        )}
      </div>
    </div>
  );
}
