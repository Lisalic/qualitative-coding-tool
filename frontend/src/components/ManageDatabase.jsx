export default function ManageDatabase({
  databases,
  selectedDatabases,
  onSelect,
  onMergeDatabases,
  mergeName,
  onMergeNameChange,
  loading,
  successMessage,
  errorMessage,
  renamingDb,
  newName,
  onNewNameChange,
  onRename,
  onStartRename,
  onCancelRename,
  onDelete,
  onView,
}) {
  return (
    <div className="database-section">
      <div className="database-selection">
        <h1
          style={{
            textAlign: "center",
            fontSize: "28px",
            fontWeight: "600",
            margin: "0 0 30px 0",
          }}
        >
          Manage Databases
        </h1>
        <div className="database-list">
          {databases.map((db) => {
            const dbName = db.name || db;
            const metadata = db.metadata;
            return (
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
                    <div className="database-info">
                      <label>
                        <input
                          type="checkbox"
                          checked={selectedDatabases.includes(dbName)}
                          onChange={() => onSelect(dbName)}
                        />
                        <strong>{dbName.replace(".db", "")}</strong>
                      </label>
                      {metadata && (
                        <div className="database-metadata">
                          <div className="metadata-row">
                            <span>
                              {metadata.total_submissions?.toLocaleString() ||
                                0}{" "}
                              Posts,{" "}
                              {metadata.total_comments?.toLocaleString() || 0}{" "}
                              Comments
                            </span>
                          </div>
                          {metadata.date_created &&
                            metadata.date_created > 0 && (
                              <div className="metadata-row">
                                <span>
                                  {(() => {
                                    try {
                                      return new Date(
                                        metadata.date_created * 1000
                                      ).toLocaleString();
                                    } catch (e) {
                                      return "Unknown";
                                    }
                                  })()}
                                </span>
                              </div>
                            )}
                        </div>
                      )}
                    </div>
                    <div className="database-actions">
                      <button
                        onClick={() => onView(dbName)}
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
                        View
                      </button>
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
            );
          })}
        </div>

        <div className="merge-controls">
          <input
            type="text"
            placeholder="Enter merged database name..."
            value={mergeName}
            onChange={(e) => onMergeNameChange(e.target.value)}
            disabled={loading}
            style={{
              width: "100%",
              padding: "12px",
              marginBottom: "10px",
              border: "1px solid #ffffff",
              borderRadius: "4px",
              backgroundColor: "#000000",
              color: "#ffffff",
              fontSize: "16px",
            }}
          />

          <button
            onClick={onMergeDatabases}
            disabled={
              selectedDatabases.length < 2 || loading || !mergeName.trim()
            }
            style={{
              backgroundColor:
                selectedDatabases.length < 2 || loading || !mergeName.trim()
                  ? "#333"
                  : "#000000",
              color: "#ffffff",
              border: "1px solid #ffffff",
              padding: "12px 24px",
              fontSize: "16px",
              cursor:
                selectedDatabases.length < 2 || loading || !mergeName.trim()
                  ? "not-allowed"
                  : "pointer",
              borderRadius: "4px",
              transition: "all 0.2s",
              width: "100%",
              textAlign: "center",
              opacity:
                selectedDatabases.length < 2 || loading || !mergeName.trim()
                  ? 0.6
                  : 1,
            }}
            onMouseOver={(e) => {
              if (
                selectedDatabases.length >= 2 &&
                !loading &&
                mergeName.trim()
              ) {
                e.target.style.backgroundColor = "#ffffff";
                e.target.style.color = "#000000";
              }
            }}
            onMouseOut={(e) => {
              if (
                selectedDatabases.length >= 2 &&
                !loading &&
                mergeName.trim()
              ) {
                e.target.style.backgroundColor = "#000000";
                e.target.style.color = "#ffffff";
              }
            }}
          >
            {loading ? "Merging..." : "Merge Databases"}
          </button>
        </div>

        {errorMessage && (
          <div
            className="error-message"
            style={{
              color: "#ff6b6b",
              backgroundColor: "#2a1a1a",
              border: "1px solid #ff6b6b",
              borderRadius: "4px",
              padding: "12px",
              marginTop: "10px",
              textAlign: "center",
              fontSize: "14px",
            }}
          >
            {errorMessage}
          </div>
        )}

        {successMessage && (
          <div className="success-message">{successMessage}</div>
        )}
      </div>
    </div>
  );
}
