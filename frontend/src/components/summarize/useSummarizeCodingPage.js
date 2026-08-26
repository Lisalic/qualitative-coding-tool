import { useEffect, useState } from "react";
import { apiFetch, postFormAndPoll } from "../../api";

export default function useSummarizeCodingPage() {
  const [codings, setCodings] = useState([]);
  const [selectedCoding, setSelectedCoding] = useState("");
  const [additionalPrompt, setAdditionalPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(null);
  const [partialWarning, setPartialWarning] = useState("");
  const [summary, setSummary] = useState("");
  const [createdFile, setCreatedFile] = useState(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/my-files/?file_type=coding")
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!mounted || !data) return;
        const list = (data.projects || []).map((project) => ({
          value: project.schema_name,
          label: project.display_name || project.schema_name,
        }));
        setCodings(list);
        if (list.length > 0) setSelectedCoding(list[0].value);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/projects/")
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!mounted || !data) return;
        setProjects(data.projects || []);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  const submitSummarize = async (event) => {
    event.preventDefault();
    setSummary("");
    setCreatedFile(null);
    setError("");
    setPartialWarning("");
    if (!selectedCoding) return setError("Select a coding to summarize");
    if (!name.trim()) return setError("Enter a name for the summary");
    if (!selectedProject) return setError("Select a project");
    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) return setError("Set your API key in the navbar first");

    const form = new FormData();
    form.append("coding", selectedCoding);
    form.append("api_key", apiKey);
    form.append("name", name.trim());
    if (model) form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());
    form.append("project_id", selectedProject);

    try {
      setLoading(true);
      setProgress(null);
      // The job also persists the summary as a File artifact directly
      // (see `name` above), so `data.file` is the created artifact -- no
      // separate save step needed.
      const { ok, data, error: pollError } = await postFormAndPoll("/api/summarize-coding/", form, {
        onProgress: setProgress,
      });
      if (!ok) {
        setError(pollError || "Failed to generate summary");
      } else {
        setSummary((data && data.summary) || "");
        setCreatedFile((data && data.file) || null);
        if (data?.partial) {
          const reason = data.partial_error
            ? `Stopped early after an error: ${data.partial_error}`
            : "This is likely due to a free model's batch limit -- use a paid model or reduce the input size for complete coverage.";
          setPartialWarning(
            `Warning: only ${data.batches_processed}/${data.batches_total} batches completed. ${reason}`,
          );
        }
      }
    } catch (submitError) {
      setError(String(submitError));
    } finally {
      setLoading(false);
    }
  };

  return {
    codings,
    selectedCoding,
    setSelectedCoding,
    additionalPrompt,
    setAdditionalPrompt,
    loading,
    progress,
    partialWarning,
    summary,
    createdFile,
    error,
    name,
    setName,
    model,
    setModel,
    projects,
    selectedProject,
    setSelectedProject,
    submitSummarize,
  };
}
