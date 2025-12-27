import { useState } from "react";
import "../styles/FileUpload.css";

export default function FileUpload({ onUploadSuccess, onView }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [subredditInput, setSubredditInput] = useState("");
  const [subredditTags, setSubredditTags] = useState([]);
  const [dataType, setDataType] = useState("posts");
  const [customName, setCustomName] = useState("");

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

    setLoading(true);
    setMessage("");
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      if (subredditTags.length > 0) {
        formData.append("subreddits", JSON.stringify(subredditTags));
      }

      formData.append("data_type", dataType);
      formData.append("name", customName.trim());

      const response = await fetch("/api/upload-zst/", {
        method: "POST",
        body: formData,
      });
      console.log("Response received:", response.status, response.statusText);

      if (!response.ok) {
        const text = await response.text();
        console.log("Error response text:", text);
        let errorMsg = "Upload failed";
        try {
          const errorData = JSON.parse(text);
          errorMsg = errorData.detail || errorMsg;
        } catch (e) {
          errorMsg = text || errorMsg;
        }
        throw new Error(errorMsg);
      }

      const text = await response.text();
      console.log("Response text:", text);
      if (!text) {
        throw new Error("Empty response from server");
      }
      const data = JSON.parse(text);
      console.log("Parsed response data:", data);

      if (data.status === "processing") {
        setMessage("📤 File uploaded. Import processing in background...");
      } else {
        setMessage(data.message || "✓ Upload completed");
      }

      setFile(null);
      setSubredditTags([]);
      setSubredditInput("");
      setDataType("posts");
      setCustomName("");
      setLoading(false);

      onUploadSuccess(data);
    } catch (err) {
      setError(`Error: ${err.message}`);
      setLoading(false);
    }
  };

  return (
    <div className="file-upload">
      <h1
        style={{
          textAlign: "center",
          fontSize: "28px",
          fontWeight: "600",
          margin: "0 0 10px 0",
        }}
      >
        Import Data
      </h1>
      <div className="action-buttons">
        <button onClick={onView} className="view-button">
          View Imported Data
        </button>
      </div>
      <div className="form-wrapper">
        <h2>Upload Data</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="zst-file">Upload .zst File</label>
            <input
              id="zst-file"
              type="file"
              accept=".zst"
              onChange={handleFileChange}
              disabled={loading}
            />
            {file && <p className="file-name">Selected: {file.name}</p>}
          </div>

          <div className="form-group">
            <label htmlFor="subreddits">Filter by Subreddits</label>
            <div className="subreddit-input-wrapper">
              <div className="subreddit-input-group">
                <input
                  id="subreddits"
                  type="text"
                  placeholder="Enter subreddit name..."
                  value={subredditInput}
                  onChange={(e) => setSubredditInput(e.target.value)}
                  onKeyDown={handleAddSubreddit}
                  disabled={loading}
                />
                <button
                  type="button"
                  className="add-btn"
                  onClick={handleAddSubredditClick}
                  disabled={loading || !subredditInput.trim()}
                >
                  Add
                </button>
              </div>
              <div className="subreddit-tags">
                {subredditTags.map((subreddit, index) => (
                  <div key={index} className="tag">
                    <span>{subreddit}</span>
                    <button
                      type="button"
                      className="tag-remove"
                      onClick={() => handleRemoveSubreddit(index)}
                      disabled={loading}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="form-group">
            <label>Data Type</label>
            <div className="radio-group">
              <div>
                <input
                  type="radio"
                  id="data-type-submissions"
                  name="data-type"
                  value="submissions"
                  checked={dataType === "posts"}
                  onChange={(e) => setDataType(e.target.value)}
                  disabled={loading}
                  style={{ display: "none" }}
                />
                <label htmlFor="data-type-submissions" className="radio-label">
                  Posts
                </label>
              </div>
              <div>
                <input
                  type="radio"
                  id="data-type-comments"
                  name="data-type"
                  value="comments"
                  checked={dataType === "comments"}
                  onChange={(e) => setDataType(e.target.value)}
                  disabled={loading}
                  style={{ display: "none" }}
                />
                <label htmlFor="data-type-comments" className="radio-label">
                  Comments
                </label>
              </div>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="custom-name">Database Name</label>
            <input
              id="custom-name"
              type="text"
              placeholder="Enter database name..."
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              disabled={loading}
            />
          </div>

          <button type="submit" disabled={loading} className="form-submit-btn">
            {loading ? "Processing..." : "Upload"}
          </button>
        </form>

        {error && <p className="error-message">{error}</p>}
        {message && <p className="success-message">{message}</p>}
      </div>
    </div>
  );
}
