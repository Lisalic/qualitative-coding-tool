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
                      style={{
                        backgroundColor: "#000000",
                        color: "#ffffff",
                        border: "1px solid #ffffff",
                        padding: "12px 24px",
                        fontSize: "16px",
                        cursor: "pointer",
                        borderRadius: "4px",
                        transition: "all 0.2s",
                        marginRight: "10px",
                      }}
                      onMouseOver={(e) => {
                        e.target.style.backgroundColor = "#ffffff";
                        e.target.style.color = "#000000";
                      }}
                      onMouseOut={(e) => {
                        e.target.style.backgroundColor = "#000000";
                        e.target.style.color = "#ffffff";
                      }}
                    >
                      Rename
                    </button>
                    <button
                      onClick={() => onDelete(dbName)}
                      style={{
                        backgroundColor: "#000000",
                        color: "#ffffff",
                        border: "1px solid #ffffff",
                        padding: "12px 24px",
                        fontSize: "16px",
                        cursor: "pointer",
                        borderRadius: "4px",
                        transition: "all 0.2s",
                      }}
                      onMouseOver={(e) => {
                        e.target.style.backgroundColor = "#ffffff";
                        e.target.style.color = "#000000";
                      }}
                      onMouseOut={(e) => {
                        e.target.style.backgroundColor = "#000000";
                        e.target.style.color = "#ffffff";
                      }}
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
          style={{
            backgroundColor:
              selectedDatabases.length === 0 || loading ? "#333" : "#000000",
            color: "#ffffff",
            border: "1px solid #ffffff",
            padding: "12px 24px",
            fontSize: "16px",
            cursor:
              selectedDatabases.length === 0 || loading
                ? "not-allowed"
                : "pointer",
            borderRadius: "4px",
            transition: "all 0.2s",
            width: "100%",
            textAlign: "center",
            opacity: selectedDatabases.length === 0 || loading ? 0.6 : 1,
          }}
          onMouseOver={(e) => {
            if (selectedDatabases.length > 0 && !loading) {
              e.target.style.backgroundColor = "#ffffff";
              e.target.style.color = "#000000";
            }
          }}
          onMouseOut={(e) => {
            if (selectedDatabases.length > 0 && !loading) {
              e.target.style.backgroundColor = "#000000";
              e.target.style.color = "#ffffff";
            }
          }}
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
