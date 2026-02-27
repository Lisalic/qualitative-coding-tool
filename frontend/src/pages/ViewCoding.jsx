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
  const [parsedCoding, setParsedCoding] = useState([]);
  const [postContents, setPostContents] = useState({});
  const [viewMode, setViewMode] = useState("text"); // "text" or "table"
  const [selectedFilterCodes, setSelectedFilterCodes] = useState([]);

  // Color assignment for codes
  const getCodeColor = (code) => {
    // Simple hash function for consistent colors
    let hash = 0;
    for (let i = 0; i < code.length; i++) {
      hash = code.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash) % 360;
    return `hsl(${hue}, 70%, 60%)`;
  };

  // Get all unique codes for legend
  const getUniqueCodes = () => {
    const codes = new Set();
    parsedCoding.forEach((post) => {
      post.codeEvidence.forEach(({ code }) => codes.add(code));
    });
    return Array.from(codes).sort();
  };

  // Get filtered coding data based on selected filter codes
  const getFilteredCoding = () => {
    if (selectedFilterCodes.length === 0) return parsedCoding;
    return parsedCoding.filter((post) =>
      post.codeEvidence.some((ev) => selectedFilterCodes.includes(ev.code)),
    );
  };

  // Highlight text in content based on code evidence using position-based approach
  const highlightContent = (content, codeEvidence) => {
    if (!content || !codeEvidence.length) return content;

    // Find all evidence matches with their positions
    const intervals = [];
    codeEvidence
      .filter(({ evidence }) => evidence)
      .forEach(({ code, evidence }) => {
        // Clean evidence: remove surrounding quotes and normalize whitespace
        const cleanEvidence = evidence
          .replace(/^["']|["']$/g, "") // Remove surrounding quotes
          .replace(/\s+/g, " ") // Normalize whitespace (multiple spaces/newlines to single space)
          .trim();

        // Find all occurrences in the original content
        let searchIndex = 0;
        while (true) {
          const index = content.indexOf(cleanEvidence, searchIndex);
          if (index === -1) break;

          intervals.push({
            start: index,
            end: index + cleanEvidence.length,
            code,
            evidence: cleanEvidence,
            length: cleanEvidence.length,
          });

          searchIndex = index + 1; // Move past this match
        }
      });

    if (intervals.length === 0) return content;

    // Sort intervals by start position
    intervals.sort((a, b) => a.start - b.start);

    // Merge overlapping intervals with priority rules
    const merged = [];
    intervals.forEach((interval) => {
      if (merged.length === 0) {
        merged.push(interval);
      } else {
        const last = merged[merged.length - 1];
        if (interval.start >= last.end) {
          // No overlap, add as separate interval
          merged.push(interval);
        } else {
          // Overlap - merge with priority rules
          // Priority: shorter evidence first (more specific), then alphabetical by code
          const shouldReplace =
            interval.length < last.length ||
            (interval.length === last.length && interval.code < last.code);

          if (shouldReplace) {
            // Replace the last interval with this one
            merged[merged.length - 1] = interval;
          }
          // Extend end if necessary
          if (interval.end > last.end) {
            merged[merged.length - 1].end = interval.end;
          }
        }
      }
    });

    // Build HTML by splitting content into segments
    let result = "";
    let lastEnd = 0;

    merged.forEach((interval) => {
      // Add unhighlighted text before this interval
      if (interval.start > lastEnd) {
        result += content.slice(lastEnd, interval.start);
      }

      // Add highlighted text
      const color = getCodeColor(interval.code);
      const highlightedText = content.slice(interval.start, interval.end);
      result += `<mark style="background-color: ${color}; color: black; padding: 2px 4px; border-radius: 3px; font-weight: bold;" title="${interval.code}: ${interval.evidence}">${highlightedText}</mark>`;

      lastEnd = interval.end;
    });

    // Add remaining unhighlighted text
    if (lastEnd < content.length) {
      result += content.slice(lastEnd);
    }

    return result;
  };

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
          codeEvidence: [],
        };
      } else if (trimmed.startsWith("CODE:") && currentPost) {
        // Parse "CODE: [code_name] - EVIDENCE: [text1]§[text2]§[text3]"
        const codeMatch = trimmed.match(
          /^CODE:\s*(.+?)\s*-\s*EVIDENCE:\s*(.+)$/,
        );
        if (codeMatch) {
          const code = codeMatch[1].trim();
          const evidenceString = codeMatch[2].trim();
          // Split evidence on § separator and create separate entries for each snippet
          const evidenceSnippets = evidenceString
            .split("§")
            .map((s) => s.trim())
            .filter((s) => s);
          evidenceSnippets.forEach((evidence) => {
            currentPost.codeEvidence.push({ code, evidence });
          });
        }
      } else if (trimmed.startsWith("CODES:") && currentPost) {
        // Backward compatibility: handle old format
        const codesStr = trimmed.replace("CODES:", "").trim();
        const codes = codesStr
          .split(",")
          .map((code) => code.trim())
          .filter((code) => code);
        // For old format, add codes without evidence
        codes.forEach((code) => {
          currentPost.codeEvidence.push({ code, evidence: "" });
        });
      }
    }

    if (currentPost) {
      parsed.push(currentPost);
    }

    console.log("Parsed coding data:", parsed);
    setParsedCoding(parsed);
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

  const renderTableView = () => (
    <div>
      {selectedFilterCodes.length > 0 && (
        <div style={{ marginBottom: "10px", color: "#fff" }}>
          <strong>Filtering by codes:</strong> {selectedFilterCodes.join(", ")}{" "}
          <button
            onClick={() => setSelectedFilterCodes([])}
            style={{
              backgroundColor: "#555",
              color: "#fff",
              border: "none",
              padding: "2px 6px",
              borderRadius: "3px",
              cursor: "pointer",
              fontSize: "0.8em",
            }}
          >
            Clear Filter
          </button>
        </div>
      )}
      {/* Color Legend */}
      <div
        style={{
          marginBottom: "20px",
          padding: "10px",
          backgroundColor: "#222",
          borderRadius: "8px",
        }}
      >
        <h4 style={{ margin: "0 0 10px 0", color: "#fff" }}>Legend</h4>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {getUniqueCodes().map((code) => (
            <div
              key={code}
              onClick={() =>
                setSelectedFilterCodes((prev) =>
                  prev.includes(code)
                    ? prev.filter((c) => c !== code)
                    : [...prev, code],
                )
              }
              style={{
                display: "flex",
                alignItems: "center",
                backgroundColor: selectedFilterCodes.includes(code)
                  ? "#555"
                  : "#333",
                padding: "4px 8px",
                borderRadius: "4px",
                fontSize: "0.9em",
                cursor: "pointer",
                border: selectedFilterCodes.includes(code)
                  ? "2px solid #fff"
                  : "none",
                transition: "background-color 0.2s",
              }}
            >
              <div
                style={{
                  width: "12px",
                  height: "12px",
                  backgroundColor: getCodeColor(code),
                  borderRadius: "2px",
                  marginRight: "6px",
                }}
              />
              <span style={{ color: "#fff" }}>{code}</span>
            </div>
          ))}
        </div>
      </div>

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
                Title
              </th>
              <th
                style={{
                  padding: "12px",
                  border: "1px solid #555",
                  textAlign: "left",
                }}
              >
                Content
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
            {getFilteredCoding().map((item, index) => (
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
                    maxWidth: "300px",
                  }}
                >
                  <div
                    style={{ whiteSpace: "pre-wrap", wordWrap: "break-word" }}
                  >
                    {(() => {
                      // Case-insensitive lookup for post content
                      const postIdLower = item.postId.toLowerCase();
                      const matchingKey = Object.keys(postContents).find(
                        (key) => key.toLowerCase() === postIdLower,
                      );
                      const postData = matchingKey
                        ? postContents[matchingKey]
                        : null;
                      console.log(
                        `Post ${item.postId}: content exists = ${!!postData} (matched key: ${matchingKey})`,
                      );
                      if (!postData) {
                        console.log(
                          `Available postContents keys:`,
                          Object.keys(postContents).slice(0, 10),
                        );
                      }
                      return postData ? postData.title : "Title not found";
                    })()}
                  </div>
                </td>
                <td
                  style={{
                    padding: "12px",
                    border: "1px solid #555",
                    verticalAlign: "top",
                    maxWidth: "400px",
                  }}
                >
                  <div
                    style={{ whiteSpace: "pre-wrap", wordWrap: "break-word" }}
                  >
                    {(() => {
                      // Case-insensitive lookup for post content
                      const postIdLower = item.postId.toLowerCase();
                      const matchingKey = Object.keys(postContents).find(
                        (key) => key.toLowerCase() === postIdLower,
                      );
                      const postData = matchingKey
                        ? postContents[matchingKey]
                        : null;
                      if (postData && postData.content) {
                        return (
                          <div
                            dangerouslySetInnerHTML={{
                              __html: highlightContent(
                                postData.content,
                                item.codeEvidence,
                              ),
                            }}
                          />
                        );
                      }
                      return "Content not found";
                    })()}
                  </div>
                </td>
                <td
                  style={{
                    padding: "12px",
                    border: "1px solid #555",
                    verticalAlign: "top",
                  }}
                >
                  {item.codeEvidence.length > 0 ? (
                    <div>
                      {[
                        ...new Set(item.codeEvidence.map(({ code }) => code)),
                      ].map((code) => (
                        <div
                          key={code}
                          style={{
                            display: "inline-block",
                            backgroundColor: getCodeColor(code),
                            color: "black",
                            padding: "4px 8px",
                            margin: "2px",
                            borderRadius: "4px",
                            fontSize: "0.9em",
                            fontWeight: "bold",
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
