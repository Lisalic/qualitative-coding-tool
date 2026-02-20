import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../api";
import SelectionList from "../components/SelectionList";
import "../styles/Data.css";
import "../styles/DataTable.css";
import MarkdownView from "../components/MarkdownView";

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
  const [viewMode, setViewMode] = useState("text"); // "text" or "table"
  const [parentData, setParentData] = useState({}); // object mapping post IDs to content
  const [parsedCoding, setParsedCoding] = useState([]); // array of {postId, codes} objects

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
      parseCodingData(codedDataContent);
      fetchParentData(selectedCodedData);
    }
  }, [codedDataContent, selectedCodedData]);

  const fetchProjects = async () => {
    try {
      const resp = await apiFetch("/api/projects/");
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

  const parseCodingData = (content) => {
    const lines = content.split("\n");
    const parsed = [];
    let currentPost = null;

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("POST_ID:")) {
        if (currentPost) {
          parsed.push(currentPost);
        }
        currentPost = {
          postId: trimmed.replace("POST_ID:", "").trim(),
          codes: [],
        };
      } else if (trimmed.startsWith("CODES:") && currentPost) {
        const codesStr = trimmed.replace("CODES:", "").trim();
        currentPost.codes = codesStr
          .split(",")
          .map((code) => code.trim())
          .filter((code) => code);
      }
    }

    if (currentPost) {
      parsed.push(currentPost);
    }

    setParsedCoding(parsed);
  };

  const fetchParentData = async (codedDataId) => {
    try {
      // Find the selected coding file to get its parent files
      const selectedFile = availableCodedData.find((f) => f.id === codedDataId);
      if (!selectedFile || !selectedFile.metadata?.file?.parent_files) {
        return;
      }

      // Find the parent database (raw_data or filtered_data)
      const parentDb = selectedFile.metadata.file.parent_files.find(
        (p) => p.type === "raw_data" || p.type === "filtered_data",
      );

      if (!parentDb) {
        return;
      }

      // Fetch data from the parent database
      const dataResp = await apiFetch(
        `/api/get-data?database=${parentDb.name}&limit=1000`,
      );
      if (!dataResp.ok) return;

      const data = await dataResp.json();
      const postMap = {};

      // Build mapping of post IDs to content
      if (data.submissions) {
        data.submissions.forEach((sub) => {
          postMap[sub.id] =
            `Title: ${sub.title || ""}\n${sub.selftext || ""}`.trim();
        });
      }

      if (data.comments) {
        data.comments.forEach((comment) => {
          postMap[comment.id] = comment.body || "";
        });
      }

      setParentData(postMap);
    } catch (err) {
      console.error("Error fetching parent data:", err);
    }
  };

  const handleCodedDataChange = (codedDataId) => {
    setSelectedCodedData(codedDataId);
    const sel = availableCodedData.find((cd) => cd.id === codedDataId);
    setSelectedCodedDataName(sel?.display_name || sel?.name || codedDataId);
  };

  const renderTableView = () => (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          backgroundColor: "#000",
          color: "#fff",
        }}
      >
        <thead>
          <tr style={{ backgroundColor: "#333" }}>
            <th
              style={{
                padding: "12px",
                border: "1px solid #555",
                textAlign: "left",
              }}
            >
              Post ID
            </th>
            <th
              style={{
                padding: "12px",
                border: "1px solid #555",
                textAlign: "left",
              }}
            >
              Post Content
            </th>
            <th
              style={{
                padding: "12px",
                border: "1px solid #555",
                textAlign: "left",
              }}
            >
              Codes Applied
            </th>
          </tr>
        </thead>
        <tbody>
          {parsedCoding.map((item, index) => (
            <tr key={index} style={{ borderBottom: "1px solid #333" }}>
              <td
                style={{
                  padding: "12px",
                  border: "1px solid #555",
                  verticalAlign: "top",
                }}
              >
                {item.postId}
              </td>
              <td
                style={{
                  padding: "12px",
                  border: "1px solid #555",
                  verticalAlign: "top",
                  maxWidth: "400px",
                }}
              >
                <div style={{ whiteSpace: "pre-wrap", wordWrap: "break-word" }}>
                  {parentData[item.postId] || "Content not found"}
                </div>
              </td>
              <td
                style={{
                  padding: "12px",
                  border: "1px solid #555",
                  verticalAlign: "top",
                }}
              >
                {item.codes.length > 0 ? (
                  <div>
                    {item.codes.map((code, codeIndex) => (
                      <div
                        key={codeIndex}
                        style={{
                          display: "inline-block",
                          backgroundColor: "#444",
                          padding: "4px 8px",
                          margin: "2px",
                          borderRadius: "4px",
                          fontSize: "0.9em",
                        }}
                      >
                        {code}
                      </div>
                    ))}
                  </div>
                ) : (
                  <span style={{ color: "#888" }}>No codes applied</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

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
              renderTableView()
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
