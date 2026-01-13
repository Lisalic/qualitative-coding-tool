import { useNavigate } from "react-router-dom";
import ErrorDisplay from "../components/ErrorDisplay";
import UploadData from "../components/UploadData";
import ManageDatabase from "../components/ManageDatabase";
import { useState, useEffect } from "react";
import "../styles/Home.css";
import "../styles/Data.css";
import { apiFetch } from "../api";

export default function Import() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [uploadData, setUploadData] = useState(null);
  const [databases, setDatabases] = useState([]);
  const [userProjects, setUserProjects] = useState(null);
  const [selectedDatabases, setSelectedDatabases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [renamingDb, setRenamingDb] = useState(null);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [mergeName, setMergeName] = useState("");
  const [mergeDescription, setMergeDescription] = useState("");

  useEffect(() => {
    fetchDatabases();
  }, []);

  const fetchDatabases = async () => {
    try {
      // Check authentication and fetch user projects if logged in
      const meResp = await apiFetch("/api/me/");
      if (meResp.ok) {
        const projResp = await apiFetch(
          "/api/my-projects/?project_type=raw_data"
        );
        if (!projResp.ok) throw new Error("Failed to fetch user projects");
        const projData = await projResp.json();
        setUserProjects(projData.projects || []);
        // normalize databases to objects with `name` and `display_name` so ManageDatabase can render
        const normalized = (projData.projects || []).map((p) => {
          const tables = p.tables || [];
          const submissionsTable = tables.find(
            (t) => t.table_name === "submissions"
          );
          const commentsTable = tables.find((t) => t.table_name === "comments");
          return {
            name: p.schema_name,
            display_name: p.display_name,
            description: p.description ?? null,
            metadata: {
              // Include created_at from projects table (ISO string)
              created_at: p.created_at || null,
              tables: tables,
              total_submissions: submissionsTable
                ? submissionsTable.row_count
                : 0,
              total_comments: commentsTable ? commentsTable.row_count : 0,
            },
          };
        });
        setDatabases(normalized);
        return;
      }

      // If not authenticated, still try to use my-projects for raw_data (may be empty)
      const response = await apiFetch(
        "/api/my-projects/?project_type=raw_data"
      );
      if (response.ok) {
        const data = await response.json();
        const normalized = (data.projects || []).map((p) => {
          const tables = p.tables || [];
          const submissionsTable = tables.find(
            (t) => t.table_name === "submissions"
          );
          const commentsTable = tables.find((t) => t.table_name === "comments");
          return {
            name: p.schema_name,
            display_name: p.display_name,
            description: p.description ?? null,
            metadata: {
              created_at: p.created_at || null,
              tables: tables,
              total_submissions: submissionsTable
                ? submissionsTable.row_count
                : 0,
              total_comments: commentsTable ? commentsTable.row_count : 0,
            },
          };
        });
        setDatabases(normalized);
        return;
      }
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
      if (mergeDescription && mergeDescription.trim()) {
        formData.append("description", mergeDescription.trim());
      }

      const response = await apiFetch("/api/merge-databases/", {
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
      setMergeDescription("");
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
      // Include credentials so project schema deletes (which require auth) work
      const response = await apiFetch(`/api/delete-database/${dbName}`, {
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
      // Determine if this is a project schema (userProjects contains schema_name)
      const isProject = (userProjects || []).some(
        (p) =>
          p.schema_name === oldName ||
          p.schema_name === oldName.replace(".db", "")
      );

      if (isProject) {
        const formData = new FormData();
        // send schema_name and display_name to rename project display name
        formData.append("schema_name", oldName);
        formData.append("display_name", newName.trim());
        // Always send description (allow clearing by sending empty string)
        formData.append(
          "description",
          newDescription == null ? "" : newDescription
        );

        const response = await apiFetch("/api/rename-project/", {
          method: "POST",
          body: formData,
        });

        if (!response.ok)
          throw new Error("Failed to rename project display name");
        const data = await response.json();
        console.log("Project renamed:", data);
      }
      setRenamingDb(null);
      setNewName("");
      setNewDescription("");
      fetchDatabases();
    } catch (err) {
      console.error("Rename error:", err);
      setError(`Error renaming database: ${err.message}`);
    }
  };

  const startRename = (dbName) => {
    setRenamingDb(dbName);
    // If this DB corresponds to a user project, prefill with its display_name
    const proj = (userProjects || []).find(
      (p) =>
        p.schema_name === dbName || p.schema_name === dbName.replace(".db", "")
    );
    if (proj && proj.display_name) {
      setNewName(proj.display_name);
      setNewDescription(proj.description || "");
    } else {
      setNewName(dbName.replace(".db", ""));
    }
  };

  const cancelRename = () => {
    setRenamingDb(null);
    setNewName("");
    setNewDescription("");
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
      <div className="home-container">
        {error &&
          !error.includes("select at least") &&
          !error.includes("enter a name") &&
          !error.includes("Database") &&
          !error.includes("merge") && (
            <ErrorDisplay message={error} onDismiss={handleDismissError} />
          )}

        <div className="tool-page-layout">
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
              mergeDescription={mergeDescription}
              onMergeDescriptionChange={setMergeDescription}
              newDescription={newDescription}
              onNewDescriptionChange={setNewDescription}
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
