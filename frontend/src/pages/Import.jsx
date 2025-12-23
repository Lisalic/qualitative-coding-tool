import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ErrorDisplay from "../components/ErrorDisplay";
import UploadData from "../components/UploadData";
import ManageDatabase from "../components/ManageDatabase";
import { useState, useEffect } from "react";
import "../styles/Home.css";
import "../styles/Data.css";

export default function Import() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [uploadData, setUploadData] = useState(null);
  const [databases, setDatabases] = useState([]);
  const [selectedDatabases, setSelectedDatabases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [renamingDb, setRenamingDb] = useState(null);
  const [newName, setNewName] = useState("");

  useEffect(() => {
    fetchDatabases();
  }, []);

  const fetchDatabases = async () => {
    try {
      const response = await fetch("/api/list-databases/");
      if (!response.ok) throw new Error("Failed to fetch databases");
      const data = await response.json();
      setDatabases(data.databases);
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  const handleDatabaseSelect = (dbName) => {
    setSelectedDatabases((prev) =>
      prev.includes(dbName)
        ? prev.filter((db) => db !== dbName)
        : [...prev, dbName]
    );
  };

  const handleCreateMaster = async () => {
    if (selectedDatabases.length === 0) return;

    setLoading(true);
    setSuccessMessage("");
    try {
      const formData = new FormData();
      formData.append("databases", JSON.stringify(selectedDatabases));

      const response = await fetch("/api/merge-databases/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Failed to create master database");

      const data = await response.json();
      console.log("Master database created:", data);
      setSuccessMessage("Master database created successfully!");
      setSelectedDatabases([]);
    } catch (err) {
      console.error("Create master error:", err);
      setError(`Error creating master database: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDatabase = async (dbName) => {
    if (!confirm(`Are you sure you want to delete the database "${dbName}"?`))
      return;

    try {
      const response = await fetch(`/api/delete-database/${dbName}`, {
        method: "DELETE",
      });

      if (!response.ok) throw new Error("Failed to delete database");

      const data = await response.json();
      console.log("Database deleted:", data);
      fetchDatabases();
    } catch (err) {
      console.error("Delete error:", err);
      setError(`Error deleting database: ${err.message}`);
    }
  };

  const handleRenameDatabase = async (oldName) => {
    if (!newName.trim()) {
      setError("New name cannot be empty");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("old_name", oldName);
      formData.append("new_name", newName.trim());

      const response = await fetch("/api/rename-database/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Failed to rename database");

      const data = await response.json();
      console.log("Database renamed:", data);
      setRenamingDb(null);
      setNewName("");
      fetchDatabases();
    } catch (err) {
      console.error("Rename error:", err);
      setError(`Error renaming database: ${err.message}`);
    }
  };

  const startRename = (dbName) => {
    setRenamingDb(dbName);
    setNewName(dbName.replace(".db", ""));
  };

  const cancelRename = () => {
    setRenamingDb(null);
    setNewName("");
  };

  const handleBack = () => {
    navigate("/");
  };

  const handleUploadSuccess = (data) => {
    setUploadData(data);
    setError("");
    fetchDatabases();
  };

  const handleUploadError = (errorMsg) => {
    setError(errorMsg);
    setUploadData(null);
  };

  const handleDismissError = () => {
    setError("");
  };

  const handleViewData = () => {
    navigate("/data");
  };

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
      <div className="home-container">
        <div className="form-wrapper">
          <h1>Import Data</h1>

          <div style={{ marginBottom: "30px", textAlign: "center" }}>
            <button
              onClick={handleViewData}
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
              View Imported Data
            </button>
          </div>

          <ErrorDisplay message={error} onDismiss={handleDismissError} />

          <div className="import-layout">
            <UploadData
              onUploadSuccess={handleUploadSuccess}
              onError={handleUploadError}
            />

            {databases.length > 0 && (
              <ManageDatabase
                databases={databases}
                selectedDatabases={selectedDatabases}
                onSelect={handleDatabaseSelect}
                onCreateMaster={handleCreateMaster}
                loading={loading}
                successMessage={successMessage}
                renamingDb={renamingDb}
                newName={newName}
                onNewNameChange={setNewName}
                onRename={handleRenameDatabase}
                onStartRename={startRename}
                onCancelRename={cancelRename}
                onDelete={handleDeleteDatabase}
              />
            )}
          </div>
        </div>
      </div>
    </>
  );
}
