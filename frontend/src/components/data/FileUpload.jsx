import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../../api";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";

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

const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";
const btnClasses =
  "border border-paper px-4 py-2 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

export default function FileUpload({ onUploadSuccess, onView }) {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [createdFile, setCreatedFile] = useState(null);
  const [error, setError] = useState("");
  const [subredditInput, setSubredditInput] = useState("");
  const [subredditTags, setSubredditTags] = useState([]);
  const [dataType, setDataType] = useState("posts");
  const [customName, setCustomName] = useState("");
  const [description, setDescription] = useState("");
  const [projects, setProjects] = useState([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectsError, setProjectsError] = useState("");
  const [selectedProject, setSelectedProject] = useState("");

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.name.endsWith(".zst")) {
      setFile(selectedFile);
      setError("");
    } else {
      setError("Please select a .zst file");
      setFile(null);
    }
  };

  const handleAddSubreddit = (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const value = subredditInput.trim().replace(/,\s*$/, "");
      if (value && !subredditTags.includes(value.toLowerCase())) {
        setSubredditTags([...subredditTags, value.toLowerCase()]);
        setSubredditInput("");
      }
    }
  };

  const handleAddSubredditClick = () => {
    const value = subredditInput.trim();
    if (value && !subredditTags.includes(value.toLowerCase())) {
      setSubredditTags([...subredditTags, value.toLowerCase()]);
      setSubredditInput("");
    }
  };

  const handleRemoveSubreddit = (index) => {
    setSubredditTags(subredditTags.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!file) {
      setError("Please select a file");
      return;
    }

    if (!customName.trim()) {
      setError("Please enter a database name");
      return;
    }

    if (!selectedProject) {
      setError("Please select a project");
      return;
    }

    setLoading(true);
    setCreatedFile(null);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      if (subredditTags.length > 0) {
        formData.append("subreddits", JSON.stringify(subredditTags));
      }

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
        let errorMsg = `Upload failed (HTTP ${response.status})`;
        try {
          const errorData = text ? JSON.parse(text) : null;
          errorMsg = formatApiErrorPayload(errorData, text || errorMsg);
        } catch (e2) {
          errorMsg = text || errorMsg;
        }
        throw new Error(errorMsg);
      }

      const text = await response.text();
      if (!text) {
        throw new Error("Empty response from server");
      }
      const data = JSON.parse(text);

      setCreatedFile(data);

      setFile(null);
      setSubredditTags([]);
      setSubredditInput("");
      setDataType("posts");
      setCustomName("");
      setDescription("");
      setSelectedProject("");
      setLoading(false);

      onUploadSuccess(data);
    } catch (err) {
      setError(`Error: ${err.message}`);
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
          let msg = `Could not load projects (HTTP ${resp.status})`;
          try {
            const d = text ? JSON.parse(text) : null;
            msg = formatApiErrorPayload(d, msg);
          } catch (_) {
            if (text) msg = text;
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
          setProjectsError(e3?.message || String(e3));
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
    <div>
      <h1 className="mb-2 text-center text-2xl font-bold">Import Data</h1>

      <div className="mb-6 flex justify-center">
        <button type="button" onClick={onView} className={btnClasses}>
          View Imported Data
        </button>
      </div>

      <h2 className="mb-4 text-xl font-semibold">Upload Data</h2>
      {projectsLoading && (
        <p className="mb-4 text-sm text-paper/70">Loading projects…</p>
      )}
      {projectsError && (
        <p className="mb-4 border border-error bg-error/10 px-4 py-3 text-sm text-error">
          {projectsError}
        </p>
      )}
      {!projectsLoading && !projectsError && projects.length === 0 && (
        <div className="mb-4 text-sm text-paper/70">
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

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="zst-file" className="text-sm">
            Upload .zst File
          </label>
          <input
            id="zst-file"
            type="file"
            accept=".zst"
            onChange={handleFileChange}
            disabled={loading}
            className="text-sm file:mr-3 file:border file:border-paper file:bg-ink file:px-3 file:py-1.5 file:text-paper file:hover:bg-paper file:hover:text-ink"
          />
          {file && <p className="text-sm text-paper/70">Selected: {file.name}</p>}
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="project-select" className="text-sm">
            Select Project
          </label>
          <select
            id="project-select"
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            disabled={
              loading ||
              projectsLoading ||
              !!projectsError ||
              projects.length === 0
            }
            required
            className={inputClasses}
          >
            <option value="" disabled>
              Select a project...
            </option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.projectname}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm">Data Type</label>
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
                className="peer hidden"
              />
              <label
                htmlFor="data-type-submissions"
                className="block cursor-pointer border border-paper px-3 py-2 text-center text-sm transition-colors hover:bg-paper hover:text-ink peer-checked:bg-paper peer-checked:text-ink"
              >
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
                className="peer hidden"
              />
              <label
                htmlFor="data-type-comments"
                className="block cursor-pointer border border-paper px-3 py-2 text-center text-sm transition-colors hover:bg-paper hover:text-ink peer-checked:bg-paper peer-checked:text-ink"
              >
                Comments
              </label>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="custom-name" className="text-sm">
            Database Name
          </label>
          <input
            id="custom-name"
            type="text"
            placeholder="Enter database name..."
            value={customName}
            onChange={(e) => setCustomName(e.target.value)}
            disabled={loading}
            className={inputClasses}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="db-description" className="text-sm">
            Description (optional)
          </label>
          <textarea
            id="db-description"
            placeholder="Optional description for this dataset..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={loading}
            rows={3}
            className={`${inputClasses} resize-y`}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="subreddit-input" className="text-sm">
            Filter by Subreddits (optional)
          </label>
          <div className="flex gap-2">
            <input
              id="subreddit-input"
              type="text"
              placeholder="Enter subreddit name..."
              value={subredditInput}
              onChange={(e) => setSubredditInput(e.target.value)}
              disabled={loading}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleAddSubredditClick();
                }
              }}
              className={`${inputClasses} flex-1`}
            />
            <button
              type="button"
              onClick={handleAddSubredditClick}
              disabled={loading || !subredditInput.trim()}
              className={btnClasses}
            >
              Add
            </button>
          </div>
          {subredditTags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {subredditTags.map((tag, index) => (
                <span
                  key={index}
                  className="flex items-center gap-1.5 border border-paper px-2.5 py-1 text-sm"
                >
                  {tag}
                  <button
                    type="button"
                    onClick={() => handleRemoveSubreddit(index)}
                    className="text-paper/70 hover:text-paper"
                    aria-label={`Remove ${tag}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={
            loading || projectsLoading || !!projectsError || projects.length === 0
          }
          className="border-2 border-paper px-6 py-3 text-base font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-50"
        >
          {loading ? "Processing..." : "Upload"}
        </button>
      </form>

      {error && (
        <p className="mt-4 border border-error bg-error/10 px-4 py-3 text-center text-sm text-error">
          {error}
        </p>
      )}
      {createdFile && (
        <div className="mt-4">
          <ArtifactCreatedMessage
            name={createdFile.display_name}
            viewPath="/data"
            viewState={{ selectedDatabase: createdFile.schema_name }}
          />
        </div>
      )}
    </div>
  );
}
