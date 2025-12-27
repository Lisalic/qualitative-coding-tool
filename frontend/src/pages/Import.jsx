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
  const [mergeName, setMergeName] = useState("");

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

  const handleMergeDatabases = async () => {
    if (selectedDatabases.length < 2) {
      setError("Please select at least 2 databases to merge");
      return;
    }

    if (!mergeName.trim()) {
      setError("Please enter a name for the merged database");
      return;
    }

    setLoading(true);
    setSuccessMessage("");
    setError(""); // Clear any previous errors
    try {
      const formData = new FormData();
      formData.append("databases", JSON.stringify(selectedDatabases));
      formData.append("name", mergeName.trim());

      const response = await fetch("/api/merge-databases/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let errorMsg = "Failed to merge databases";
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorMsg;
        } catch (e) {
          // If we can't parse JSON, use the generic message
        }
        throw new Error(errorMsg);
      }

      const data = await response.json();
      console.log("Databases merged:", data);
      setSuccessMessage("Databases merged successfully!");
      setSelectedDatabases([]);
      setMergeName("");
      fetchDatabases();
    } catch (err) {
      console.error("Merge error:", err);
      setError(err.message); // Set the error message for display in ManageDatabase
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

  const handleUploadSuccess = (data) => {
    setUploadData(data);
    setError("");
    fetchDatabases();
  };

  const handleDismissError = () => {
    setError("");
  };

  const handleViewData = (dbName) => {
    navigate("/data", { state: { selectedDatabase: dbName } });
  };

  return (
    <>
      <Navbar showBack={true} />
      <div className="home-container">
        {error &&
          !error.includes("select at least") &&
          !error.includes("enter a name") &&
          !error.includes("Database") &&
          !error.includes("merge") && (
            <ErrorDisplay message={error} onDismiss={handleDismissError} />
          )}

        <div className="import-layout">
          <UploadData
            onUploadSuccess={handleUploadSuccess}
            onView={handleViewData}
          />

          {databases.length > 0 && (
            <ManageDatabase
              databases={databases}
              selectedDatabases={selectedDatabases}
              onSelect={handleDatabaseSelect}
              onMergeDatabases={handleMergeDatabases}
              mergeName={mergeName}
              onMergeNameChange={setMergeName}
              loading={loading}
              successMessage={successMessage}
              errorMessage={error}
              renamingDb={renamingDb}
              newName={newName}
              onNewNameChange={setNewName}
              onRename={handleRenameDatabase}
              onStartRename={startRename}
              onCancelRename={cancelRename}
              onDelete={handleDeleteDatabase}
              onView={handleViewData}
            />
          )}
        </div>
      </div>
    </>
  );
}
