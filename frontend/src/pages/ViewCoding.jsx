import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../api";
import SelectionList from "../components/SelectionList";
import HighlightedContent from "../components/HighlightedContent";
import CodingTableView from "../components/CodingTableView";
import "../styles/Data.css";
import "../styles/DataTable.css";
import MarkdownView from "../components/MarkdownView";
import {
  getCodeColor,
  getUniqueCodes,
  getFilteredCoding,
  parseCodingData,
} from "../lib/codingUtils";

export default function ViewCoding() {
  const location = useLocation();
  const [availableCodedData, setAvailableCodedData] = useState([]);
  const [selectedCodedData, setSelectedCodedData] = useState(null);
  const [selectedCodedDataName, setSelectedCodedDataName] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [codedDataContent, setCodedDataContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [parsedCoding, setParsedCoding] = useState([]);
  const [postContents, setPostContents] = useState({});
  const [viewMode, setViewMode] = useState("text"); // "text" or "table"
  const [selectedFilterCodes, setSelectedFilterCodes] = useState([]);

  const fetchAvailableCodedData = async () => {
    try {
      // Prefer project-backed files when a project is selected
      if (projectsList && projectsList.length > 0 && selectedProject) {
        const projectObj = projectsList.find(
          (p) => String(p.id) === String(selectedProject),
        );
        const files = (projectObj && projectObj.files) || [];
        const codingFiles = files
          .filter(
            (f) =>
              f.file_type === "coding" || f.file_type === "coding_comparison",
          )
          .map((f) => ({
            id: String(f.id),
            name: f.display_name || f.schema_name || String(f.id),
            display_name: f.display_name,
            description: f.description || null,
            metadata: { schema: f.schema_name, file: f },
            source: "project",
          }));
        setAvailableCodedData(codingFiles);
        // Do not auto-select; require the user to pick a coded data file.
        // If caller provided a preselected coded data via location.state, respect it.
        const pre = location?.state?.selectedCodedData;
        if (pre) {
          const match = codingFiles.find((it) => it.id === pre);
          if (match) {
            setSelectedCodedData(match.id);
            setSelectedCodedDataName(
              match?.display_name || match?.name || match?.id || "",
            );
          }
        }
        return;
      }

      // Prefer user-owned coded projects from Postgres
      const resp = await apiFetch("/api/my-files/?file_type=coding");
      if (resp.ok) {
        const json = await resp.json();
        const projects = json.projects || [];
        // map to the shape SelectionList expects
        const items = projects.map((p) => ({
          id: p.schema_name || p.id,
          name: p.display_name || p.schema_name || p.id,
          display_name: p.display_name,
          description: p.description || null,
          metadata: { schema: p.schema_name, file: p },
          source: "project",
        }));
        setAvailableCodedData(items);
        // Do not auto-select; only respect an explicit preselection via location.state
        if (items.length > 0) {
          const pre = location?.state?.selectedCodedData;
          if (pre) {
            const match = items.find((it) => it.id === pre);
            if (match) {
              setSelectedCodedData(match.id);
              setSelectedCodedDataName(
                match?.display_name || match?.name || match?.id || "",
              );
            }
          }
        }
        return;
      }

      // If project-backed listing fails, expose empty list (no filesystem fallback)
      console.warn("Failed to fetch coded data list; no coded data available");
      setAvailableCodedData([]);
      setSelectedCodedData(null);
      setSelectedCodedDataName("");
    } catch (err) {
      console.error("Error fetching coded data list:", err);
    }
  };

  const fetchCodedData = async (codedDataId) => {
    try {
      setLoading(true);
      const response = await apiFetch(
        `/api/coded-data?coded_id=${codedDataId}`,
      );
      if (!response.ok) {
        throw new Error("Failed to fetch coded data");
      }
      const data = await response.json();
      if (data.coded_data) {
        setCodedDataContent(data.coded_data);
        setSystemPrompt(data.systemprompt || "");
        setUserPrompt(data.userprompt || "");
      } else {
        setCodedDataContent("");
        setSystemPrompt("");
        setUserPrompt("");
      }
    } catch (err) {
      console.error("Error fetching coded data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAvailableCodedData();
    fetchProjects();
  }, []);

  // Refresh available coded data when project selection or projects list changes
  useEffect(() => {
    fetchAvailableCodedData();
  }, [selectedProject, projectsList]);

  useEffect(() => {
    if (selectedCodedData) {
      fetchCodedData(selectedCodedData);
    }
  }, [selectedCodedData]);

  useEffect(() => {
    if (codedDataContent && selectedCodedData) {
      setParsedCoding(parseCodingData(codedDataContent));
    }
  }, [codedDataContent, selectedCodedData]);

  useEffect(() => {
    if (parsedCoding.length > 0 && selectedCodedData) {
      console.log(
        "useEffect triggered: parsedCoding has",
        parsedCoding.length,
        "items",
      );
      fetchPostContents(selectedCodedData);
    } else {
      console.log(
        "useEffect not triggered: parsedCoding.length =",
        parsedCoding.length,
        "selectedCodedData =",
        selectedCodedData,
      );
    }
  }, [parsedCoding, selectedCodedData]);

  // Hide tooltip on scroll to prevent detached positioning
  useEffect(() => {
    const handleScroll = () => {
      setTooltip({ show: false, content: [], x: 0, y: 0 });
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const fetchProjects = async () => {
    try {
      const resp = await apiFetch("/api/projects/", { cache: "no-cache" });
      if (!resp.ok) return;
      const data = await resp.json();
      const projects = data.projects || [];
      setProjectsList(projects);
      // Default to 'All Projects' (no project selected)
      if (!selectedProject) setSelectedProject("");
    } catch (e) {
      console.error("Error fetching projects:", e);
    }
  };

  const fetchPostContents = async (codedDataId) => {
    console.log("fetchPostContents called with codedDataId:", codedDataId);
    try {
      // Find the selected coding file to get its parent files
      const selectedFile = availableCodedData.find((f) => f.id === codedDataId);
      console.log("selectedFile:", selectedFile);
      if (!selectedFile || !selectedFile.metadata?.file?.parent_files) {
        console.log("No selected file or parent files", selectedFile);
        return;
      }

      // Find the parent database (raw_data or filtered_data)
      const parentDb = selectedFile.metadata.file.parent_files.find(
        (p) => p.type === "raw_data" || p.type === "filtered_data",
      );
      console.log("parentDb:", parentDb);

      if (!parentDb) {
        console.log(
          "No parent database found",
          selectedFile.metadata.file.parent_files,
        );
        return;
      }

      console.log("Found parent DB:", parentDb);
      console.log("Schema name:", parentDb.schema_name);
      console.log("Name:", parentDb.name);

      // Use schema_name if available, otherwise try to construct schema name from name
      const schemaName =
        parentDb.schema_name ||
        (parentDb.name.startsWith("proj_") ? parentDb.name : null);
      console.log("Final schema name:", schemaName);
      if (!schemaName) {
        console.log("No schema name available");
        return;
      }

      // Collect unique post IDs from parsed coding
      const postIds = [...new Set(parsedCoding.map((post) => post.postId))];

      if (postIds.length === 0) {
        console.log("No post IDs found");
        return;
      }

      console.log(
        "Fetching contents for post IDs:",
        postIds,
        "in schema:",
        schemaName,
      );

      // Call the backend endpoint
      const resp = await apiFetch("/api/post-contents/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ schema: schemaName, post_ids: postIds }),
        cache: "no-cache",
      });
      console.log("API response status:", resp.status);

      if (!resp.ok) {
        console.log("API call failed:", resp.status);
        const errorText = await resp.text();
        console.log("Error response:", errorText);
        return;
      }

      const data = await resp.json();
      console.log(
        "Fetched post contents:",
        Object.keys(data.contents || {}).length,
        "posts",
      );
      setPostContents(data.contents || {});
    } catch (error) {
      console.error("Error fetching post contents:", error);
    }
  };

  const handleCodedDataChange = (codedDataId) => {
    setSelectedCodedData(codedDataId);
    const sel = availableCodedData.find((cd) => cd.id === codedDataId);
    setSelectedCodedDataName(sel?.display_name || sel?.name || codedDataId);
  };

  return (
    <>
      <div className="data-container">
        <div style={{ marginBottom: 12 }}>
          <label style={{ color: "#fff", marginRight: 8 }}>Project:</label>
          <select
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            style={{ padding: "6px 8px", borderRadius: 6 }}
          >
            <option value="">All Projects</option>
            {(projectsList || []).map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.projectname || p.display_name || p.id}
              </option>
            ))}
          </select>
        </div>
        <SelectionList
          items={availableCodedData}
          selectedId={selectedCodedData}
          onSelect={(id) => handleCodedDataChange(id)}
          className="codebook-selector"
          buttonClass="db-button"
          emptyMessage="No coded data available"
        />

        <div
          style={{
            border: "1px solid #ffffff",
            borderRadius: "8px",
            padding: "20px",
            backgroundColor: "#000000",
          }}
        >
          {selectedCodedData && (
            <div style={{ marginBottom: "16px", display: "flex", gap: "8px" }}>
              <button
                onClick={() => setViewMode("text")}
                className={viewMode === "text" ? "project-tab" : "db-button"}
                style={{ padding: "8px 16px" }}
              >
                Text View
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={viewMode === "table" ? "project-tab" : "db-button"}
                style={{ padding: "8px 16px" }}
              >
                Table View
              </button>
            </div>
          )}
          {selectedCodedData ? (
            viewMode === "text" ? (
              <MarkdownView
                key={
                  selectedCodedData
                    ? `${selectedCodedData}-${refreshKey}`
                    : `none-${refreshKey}`
                }
                selectedId={selectedCodedData}
                title={selectedCodedDataName}
                description={
                  availableCodedData.find((cd) => cd.id === selectedCodedData)
                    ?.description
                }
                fetchStyle="query"
                fetchBase="/api/coded-data"
                queryParamName="coded_id"
                saveUrl={"/api/save-file-coded-data/"}
                saveIdFieldName={"schema_name"}
                saveAsProject={true}
                projectSchema={selectedCodedData}
                systemPrompt={systemPrompt}
                userPrompt={userPrompt}
                onSaved={(resp) => {
                  if (typeof resp === "string") {
                    if (resp !== selectedCodedData) {
                      setSelectedCodedData(resp);
                      fetchAvailableCodedData();
                    }
                  } else if (resp && resp.display_name) {
                    setSelectedCodedDataName(resp.display_name);
                    fetchAvailableCodedData();
                  }
                  // force remount/refresh of MarkdownView to reload content
                  setRefreshKey((k) => k + 1);
                }}
                emptyLabel="View Coding"
              />
            ) : (
              <CodingTableView
                parsedCoding={parsedCoding}
                postContents={postContents}
                selectedFilterCodes={selectedFilterCodes}
                setSelectedFilterCodes={setSelectedFilterCodes}
                getCodeColor={getCodeColor}
                highlightContent={(content, codeEvidence) => (
                  <HighlightedContent
                    content={content}
                    codeEvidence={codeEvidence}
                    getCodeColor={getCodeColor}
                  />
                )}
              />
            )
          ) : (
            <div style={{ color: "#888", padding: 20 }}>
              Select a coded data file to view
            </div>
          )}
        </div>
      </div>
    </>
  );
}
