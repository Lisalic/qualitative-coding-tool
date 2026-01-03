import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
import PromptManager from "../components/PromptManager";
import ManageDatabase from "../components/ManageDatabase";
import { useState, useEffect } from "react";
import "../styles/Home.css";

export default function Filter() {
  const navigate = useNavigate();
  const [filterPrompt, setFilterPrompt] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [database, setDatabase] = useState("");
  const [databases, setDatabases] = useState([]); // raw data projects for selection
  const [filteredDatabases, setFilteredDatabases] = useState([]); // filtered projects for ManageDatabase
  const [name, setName] = useState("");
  const [rightView, setRightView] = useState("prompts"); // 'prompts' or 'database'
  const [renamingDb, setRenamingDb] = useState(null);
  const [newName, setNewName] = useState("");

  const EXAMPLE_PROMPT = `You are a filter-only assistant. For each input item, decide whether it should be kept or removed. Apply these rules: remove spam/automated posts, remove obvious duplicates, and remove non-topical noise. Keep authentic human discussion and on-topic content.`;

  const handleViewFilteredData = () => {
    navigate("/filtered-data");
  };

  const handleLoadPrompt = (prompt) => {
    setFilterPrompt(prompt);
  };

  useEffect(() => {
    fetchDatabases();
  }, []);

  useEffect(() => {
    if (databases.length > 0 && !database) {
      setDatabase(databases[0]);
    }
  }, [databases]);

  const fetchDatabases = async () => {
    try {
      // Fetch raw_data projects for the database select
      const respRaw = await fetch("/api/my-projects/?project_type=raw_data", {
        credentials: "include",
      });
      if (!respRaw.ok) throw new Error("Failed to fetch raw projects");
      const rawData = await respRaw.json();
      const rawOptions = (rawData.projects || []).map((p) => ({
        value: p.schema_name,
        label: p.display_name || p.schema_name,
        meta: p,
      }));

      // Fetch filtered_data projects for ManageDatabase view
      const respFiltered = await fetch(
        "/api/my-projects/?project_type=filtered_data",
        { credentials: "include" }
      );
      if (!respFiltered.ok)
        throw new Error("Failed to fetch filtered projects");
      const filtData = await respFiltered.json();
      const filtOptions = (filtData.projects || []).map((p) => ({
        value: p.schema_name,
        label: p.display_name || p.schema_name,
        meta: p,
      }));

      setDatabases(rawOptions);
      setFilteredDatabases(filtOptions);
      if (!database && rawOptions.length > 0) setDatabase(rawOptions[0].value);
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  const startRename = (dbName) => {
    setRenamingDb(dbName);
    const proj = filteredDatabases.find((d) => d.value === dbName);
    if (proj && proj.label) setNewName(proj.label);
    else setNewName(dbName.replace(".db", ""));
  };

  const cancelRename = () => {
    setRenamingDb(null);
    setNewName("");
  };

  const handleRenameDatabase = async (oldName) => {
    if (!newName.trim()) {
      setMessage("New name cannot be empty");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("schema_name", oldName);
      formData.append("display_name", newName.trim());

      const response = await fetch("/api/rename-project/", {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        let errMsg = "Failed to rename project";
        try {
          const errData = await response.json();
          errMsg = errData.detail || errMsg;
        } catch (e) {}
        throw new Error(errMsg);
      }

      setRenamingDb(null);
      setNewName("");
      // refresh lists
      await fetchDatabases();
    } catch (err) {
      console.error("Rename error:", err);
      setMessage(`Error renaming database: ${err.message}`);
    }
  };

  const handleDeleteDatabase = async (dbName) => {
    if (!confirm(`Are you sure you want to delete the database "${dbName}"?`))
      return;

    try {
      const response = await fetch(`/api/delete-database/${dbName}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!response.ok) {
        let errMsg = "Failed to delete database";
        try {
          const data = await response.json();
          errMsg = data.detail || errMsg;
        } catch (e) {}
        throw new Error(errMsg);
      }

      setMessage(`Deleted ${dbName}`);
      await fetchDatabases();
    } catch (err) {
      console.error("Delete error:", err);
      setMessage(`Error deleting database: ${err.message}`);
    }
  };

  // (filtered databases removed - only unfiltered databases are used in this page)

  const handleFieldChange = (fieldId, value) => {
    if (fieldId === "filterPrompt") {
      setFilterPrompt(value);
    }
    if (fieldId === "database") {
      setDatabase(value);
    }
    if (fieldId === "name") {
      setName(value);
    }
  };

  const handleSubmit = async (formData) => {
    const savedApiKey = localStorage.getItem("apiKey");
    if (!savedApiKey) {
      throw new Error("Please set your API key in the navbar first.");
    }

    if (!formData.filterPrompt.trim()) {
      throw new Error("Please enter a filter prompt");
    }

    // Require a name for the filtered DB
    if (!formData.name || !formData.name.trim()) {
      throw new Error("Please provide a name for the filtered database");
    }

    setLoading(true);
    setMessage("");

    try {
      const requestData = new FormData();
      requestData.append("api_key", savedApiKey);
      requestData.append("prompt", formData.filterPrompt);
      // include desired output name if provided
      if (formData.name) {
        requestData.append("name", formData.name);
      }
      // include selected database if provided
      if (formData.database) {
        requestData.append("database", formData.database);
      }

      const response = await fetch("/api/filter-data/", {
        method: "POST",
        body: requestData,
        credentials: "include",
      });

      if (!response.ok) {
        const text = await response.text();
        let errorMsg = "Filtering failed";
        try {
          const errorData = JSON.parse(text);
          errorMsg = errorData.detail || errorMsg;
        } catch (e) {
          errorMsg = text || errorMsg;
        }
        throw new Error(errorMsg);
      }

      const text = await response.text();
      const data = JSON.parse(text);

      setMessage(`✓ ${data.message}`);
      setFilterPrompt("");
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fields = [
    {
      id: "filterPrompt",
      label: "Enter prompt",
      type: "textarea",
      value: filterPrompt,
      placeholder: "Enter your filter prompt...",
      rows: 5,
      extraButton: {
        label: "Load example prompt",
        onClick: () => setFilterPrompt(EXAMPLE_PROMPT),
        className: "load-prompt-btn",
      },
    },
  ];

  const nameField = {
    id: "name",
    label: "Filtered Database Name",
    type: "text",
    value: name,
    placeholder: "my-filtered-db",
  };

  const databaseFields = [
    {
      id: "database",
      label: "Database",
      type: "select",
      value: database,
      options: databases.map((d) => ({
        value: d.value,
        label: d.label,
      })),
    },
  ];

  return (
    <>
      <Navbar showBack={true} />
      <div className="home-container">
        <div className="tool-page-layout">
          <div className="left-section">
            <div className="file-upload">
              <h1
                style={{
                  textAlign: "center",
                  fontSize: "28px",
                  fontWeight: "600",
                  margin: "0 0 10px 0",
                }}
              >
                Apply Filter
              </h1>
              <div className="action-buttons">
                <button
                  onClick={handleViewFilteredData}
                  className="view-button"
                >
                  View Filtered Data
                </button>
              </div>
              <ActionForm
                fields={[...databaseFields, nameField, ...fields]}
                submitButton={{
                  text: "Filter",
                  loadingText: "Processing...",
                  disabled: loading,
                }}
                onSubmit={handleSubmit}
                error={message && message.startsWith("Error:") ? message : null}
                result={message && message.startsWith("✓") ? message : null}
                resultTitle="Filter Result"
              />
            </div>
          </div>
          <div className="prompt-manager-section">
            <div className="prompt-manager-controls">
              <div className="left-group">
                <button
                  className={rightView === "prompts" ? "active" : ""}
                  onClick={() => setRightView("prompts")}
                >
                  Manage Prompts
                </button>
              </div>
              <div className="right-group">
                <button
                  className={rightView === "database" ? "active" : ""}
                  onClick={() => setRightView("database")}
                >
                  Manage Database
                </button>
              </div>
            </div>

            {rightView === "prompts" ? (
              <PromptManager
                onLoadPrompt={handleLoadPrompt}
                currentPrompt={filterPrompt}
              />
            ) : (
              <ManageDatabase
                databases={filteredDatabases.map((d) => ({
                  name: d.value,
                  display_name: d.label,
                  metadata: d.meta,
                }))}
                selectedDatabases={[]}
                onSelect={() => {}}
                onMergeDatabases={() => {}}
                mergeName={""}
                onMergeNameChange={() => {}}
                loading={false}
                successMessage={null}
                errorMessage={message}
                renamingDb={renamingDb}
                newName={newName}
                onNewNameChange={(v) => setNewName(v)}
                onRename={(oldName) => handleRenameDatabase(oldName)}
                onStartRename={(dbName) => startRename(dbName)}
                onCancelRename={() => cancelRename()}
                onDelete={(dbName) => handleDeleteDatabase(dbName)}
                onView={(dbName) => {
                  setDatabase(dbName);
                  navigate("/filtered-data", {
                    state: { selectedDatabase: dbName },
                  });
                }}
              />
            )}
          </div>
        </div>
      </div>
    </>
  );
}
