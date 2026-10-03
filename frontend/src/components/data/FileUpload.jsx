import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../../api";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import Panel from "../shell/Panel";
import Dropdown from "../primitives/Dropdown";
import { btn, btnPrimary, input, pillRadioInput, pillRadioLabel, select } from "../../lib/uiClasses";
import { toProjectOptions } from "../../lib/projectOptions";
import { describeSkippedRecords } from "../../lib/importSummary";

function formatApiErrorPayload(parsed, fallback) {
  if (!parsed || typeof parsed !== "object") return fallback;
  if (typeof parsed.error === "string") return parsed.error;
  if (typeof parsed.detail === "string") return parsed.detail;
  if (Array.isArray(parsed.detail)) {
    const msg = parsed.detail
      .map((d) => {
        const loc = Array.isArray(d.loc) ? d.loc.slice(-1).join(".") : "";
        return loc ? `${loc}: ${d.msg}` : d.msg;
      })
      .filter(Boolean)
      .join("; ");
    return msg || fallback;
  }
  return fallback;
}

const inputClasses = input;
const selectClasses = select;
const btnClasses = btn;

export default function FileUpload({ onUploadSuccess }) {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [createdFile, setCreatedFile] = useState(null);
  const [error, setError] = useState("");
  const [dataType, setDataType] = useState("posts");
  const [customName, setCustomName] = useState("");
  const [description, setDescription] = useState("");
  const [projects, setProjects] = useState([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState("");
  const [selectedProject, setSelectedProject] = useState("");
  // Validation messages keyed by field, shown next to the field itself.
  const [fieldErrors, setFieldErrors] = useState({});
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.name.endsWith(".zst")) {
      setFile(selectedFile);
      setFieldErrors((prev) => ({ ...prev, file: undefined }));
    } else {
      setFieldErrors((prev) => ({ ...prev, file: "Choose a .zst file." }));
      setFile(null);
      // Clear the native input too, or it keeps showing the rejected file.
      e.target.value = "";
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const nextFieldErrors = {};
    if (!file) nextFieldErrors.file = "Choose a .zst file to import.";
    if (!selectedProject) nextFieldErrors.project = "Choose a project.";
    if (!customName.trim()) nextFieldErrors.name = "Enter a name for the database.";
    setFieldErrors(nextFieldErrors);
    if (Object.keys(nextFieldErrors).length > 0) return;

    setLoading(true);
    setCreatedFile(null);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("data_type", dataType);
      formData.append("name", customName.trim());
      if (description && description.trim()) {
        formData.append("description", description.trim());
      }
      if (selectedProject) {
        formData.append("project_id", selectedProject);
      }

      const response = await apiFetch("/api/upload-zst/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const text = await response.text();
        let errorMsg =
          response.status >= 500
            ? `The upload failed on the server (HTTP ${response.status}). Please try again.`
            : `The upload failed (HTTP ${response.status}).`;
        try {
          const errorData = text ? JSON.parse(text) : null;
          errorMsg = formatApiErrorPayload(errorData, errorMsg);
        } catch {
          // Not JSON (e.g. a proxy's HTML error page) -- keep the plain message.
        }
        throw new Error(errorMsg);
      }

      const text = await response.text();
      if (!text) {
        throw new Error("The server didn't confirm the upload. Check your project before trying again.");
      }
      const data = JSON.parse(text);

      setCreatedFile(data);

      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setDataType("posts");
      setCustomName("");
      setDescription("");
      setSelectedProject("");
      setLoading(false);

      onUploadSuccess(data);
    } catch (err) {
      setError(err?.message || "The upload failed. Please try again.");
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;
    async function loadProjects() {
      setProjectsLoading(true);
      setProjectsError("");
      try {
        const resp = await apiFetch("/api/projects/");
        if (!mounted) return;
        if (!resp.ok) {
          const text = await resp.text();
          let msg = `Couldn't load your projects (HTTP ${resp.status}). Please refresh to try again.`;
          try {
            const d = text ? JSON.parse(text) : null;
            msg = formatApiErrorPayload(d, msg);
          } catch {
            // Not JSON -- keep the plain message.
          }
          setProjectsError(msg);
          setProjects([]);
          setProjectsLoading(false);
          return;
        }
        const text = await resp.text();
        if (!text) {
          setProjects([]);
          setProjectsLoading(false);
          return;
        }
        const data = JSON.parse(text);
        setProjects(Array.isArray(data.projects) ? data.projects : []);
      } catch (e3) {
        if (mounted) {
          console.error("Error loading projects:", e3);
          setProjectsError("Couldn't reach the server to load your projects. Check your connection and refresh.");
          setProjects([]);
        }
      } finally {
        if (mounted) setProjectsLoading(false);
      }
    }
    loadProjects();
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="flex flex-col gap-3">
      {projectsLoading && (
        <p className="text-sm text-paper/70">Loading projects…</p>
      )}
      {projectsError && (
        <p role="alert" className="border border-error bg-error/10 px-3 py-2 text-sm text-error">
          {projectsError}
        </p>
      )}
      {!projectsLoading && !projectsError && projects.length === 0 && (
        <div className="text-sm text-paper/70">
          <p className="mb-3">
            You need at least one project before you can import data. Create a
            project from the home page, then return here.
          </p>
          <button
            type="button"
            className={btnClasses}
            onClick={() => navigate("/")}
          >
            Go to home
          </button>
        </div>
      )}

      {/* Two columns rather than one tall stack: the form has two natural
          halves (what is being read, and where it lands), and a single
          column left most of a wide page empty. */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 lg:flex-row">
          <Panel
            title="Source file"
            className="flex-1"
            scroll={false}
            bodyClassName="flex flex-col gap-3"
          >
            <div className="flex flex-col gap-1.5">
              <label htmlFor="zst-file" className="text-sm">
                Data file (.zst)
              </label>
              <input
                ref={fileInputRef}
                id="zst-file"
                type="file"
                aria-describedby="zst-file-help"
                accept=".zst"
                onChange={handleFileChange}
                disabled={loading}
                className="text-sm file:mr-3 file:border file:border-paper file:bg-ink file:px-3 file:py-1.5 file:text-paper file:hover:bg-paper file:hover:text-ink"
              />
              <p id="zst-file-help" className="text-xs text-paper/50">
                A zstandard-compressed file of posts or comments, one JSON record per line.
              </p>
              {fieldErrors.file ? <p className="text-xs text-error">{fieldErrors.file}</p> : null}
              {file && (
                <p className="text-sm text-paper/70">Selected: {file.name}</p>
              )}
            </div>

            <fieldset className="min-w-0">
              <legend className="mb-1.5 text-sm">Data type</legend>
              <div className="flex w-full gap-2">
                <div className="flex-1">
                  <input
                    type="radio"
                    id="data-type-submissions"
                    name="data-type"
                    value="posts"
                    checked={dataType === "posts"}
                    onChange={(e) => setDataType(e.target.value)}
                    disabled={loading}
                    className={pillRadioInput}
                  />
                  <label htmlFor="data-type-submissions" className={pillRadioLabel}>
                    Posts
                  </label>
                </div>
                <div className="flex-1">
                  <input
                    type="radio"
                    id="data-type-comments"
                    name="data-type"
                    value="comments"
                    checked={dataType === "comments"}
                    onChange={(e) => setDataType(e.target.value)}
                    disabled={loading}
                    className={pillRadioInput}
                  />
                  <label htmlFor="data-type-comments" className={pillRadioLabel}>
                    Comments
                  </label>
                </div>
              </div>
            </fieldset>
          </Panel>

          <Panel
            title="Destination"
            className="flex-1"
            scroll={false}
            bodyClassName="flex flex-col gap-3"
          >
            <div className="flex flex-col gap-1.5">
              <label htmlFor="project-select" className="text-sm">
                Project
              </label>
              <Dropdown
                id="project-select"
                value={selectedProject}
                options={toProjectOptions(projects)}
                onChange={setSelectedProject}
                placeholder="Select a project"
                disabled={
                  loading ||
                  projectsLoading ||
                  !!projectsError ||
                  projects.length === 0
                }
                triggerClassName={`w-full ${selectClasses}`}
                listLabel="Project"
                searchPlaceholder="Search projects…"
                emptyMessage="No projects match that search."
              />
              {fieldErrors.project ? <p className="text-xs text-error">{fieldErrors.project}</p> : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="custom-name" className="text-sm">
                Database name
              </label>
              <input
                id="custom-name"
                type="text"
                placeholder="my-dataset"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                disabled={loading}
                className={inputClasses}
              />
              {fieldErrors.name ? <p className="text-xs text-error">{fieldErrors.name}</p> : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="db-description" className="text-sm">
                Description (optional)
              </label>
              <textarea
                id="db-description"
                placeholder="What this dataset is, where it came from…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={loading}
                rows={3}
                className={`${inputClasses} resize-y`}
              />
            </div>
          </Panel>
        </div>

        <div className="flex justify-center">
          <button
            type="submit"
            disabled={
              loading ||
              projectsLoading ||
              !!projectsError ||
              projects.length === 0
            }
            className={btnPrimary}
          >
            {loading ? "Importing…" : "Import"}
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="border border-error bg-error/10 px-3 py-2 text-center text-sm text-error">
          {error}
        </p>
      )}
      {createdFile && (
        <div>
          <ArtifactCreatedMessage
            name={createdFile.display_name}
            viewPath="/data"
            viewState={{ selectedDatabase: createdFile.schema_name }}
          />
          {Object.values(createdFile.inserted_counts || {}).every((count) => !count) && (
            <p className="mt-2 border border-error bg-error/10 px-3 py-2 text-sm text-error">
              No rows were imported. Check that the data type matches the file (posts vs comments) and that
              its posts have body text.
            </p>
          )}
          {describeSkippedRecords(createdFile.skipped_counts) && (
            <p className="mt-2 border border-line px-3 py-2 text-sm text-paper/70">
              {describeSkippedRecords(createdFile.skipped_counts)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
