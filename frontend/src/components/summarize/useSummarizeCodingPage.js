import { useEffect, useState } from "react";
import { apiFetch, postFormAndPoll } from "../../api";

export default function useSummarizeCodingPage() {
  const [codings, setCodings] = useState([]);
  const [selectedCoding, setSelectedCoding] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [additionalPrompt, setAdditionalPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState("");
  const [error, setError] = useState("");
  const [saveName, setSaveName] = useState("");
  const [saveDescription, setSaveDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState("");
  const [saveError, setSaveError] = useState("");
  const [model, setModel] = useState("");

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
        setProjects(Array.isArray(data.projects) ? data.projects : []);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  const submitSummarize = async (event) => {
    event.preventDefault();
    setSummary("");
    setError("");
    if (!selectedCoding) return setError("Select a coding to summarize");
    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) return setError("Set your API key in the navbar first");

    const form = new FormData();
    form.append("coding", selectedCoding);
    form.append("api_key", apiKey);
    if (model) form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());
    if (selectedProject) form.append("project_id", selectedProject);

    try {
      setLoading(true);
      const { ok, data, error: pollError } = await postFormAndPoll("/api/summarize-coding/", form);
      if (!ok) {
        setError(pollError || "Failed to generate summary");
      } else {
        setSummary((data && data.summary) || "");
      }
    } catch (submitError) {
      setError(String(submitError));
    } finally {
      setLoading(false);
    }
  };

  const saveSummaryToProject = async (event) => {
    event?.preventDefault();
    setSaveError("");
    setSaveSuccess("");
    if (!saveName || !saveName.trim()) {
      return setSaveError("Provide a name for the summary");
    }
    if (!selectedProject) {
      return setSaveError("Select a project to attach the summary to");
    }

    try {
      setSaving(true);
      const form = new FormData();
      form.append("content", summary || "");
      form.append("name", saveName.trim());
      form.append("description", saveDescription || "");
      form.append("project_id", String(selectedProject));

      const response = await apiFetch("/api/save-summary/", {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || data.error || `HTTP ${response.status}`);
      }
      await response.json();
      setSaveSuccess("Saved summary to project");
      setSaveName("");
      setSaveDescription("");
    } catch (saveErrorValue) {
      setSaveError(String(saveErrorValue));
    } finally {
      setSaving(false);
    }
  };

  return {
    codings,
    selectedCoding,
    setSelectedCoding,
    projects,
    selectedProject,
    setSelectedProject,
    additionalPrompt,
    setAdditionalPrompt,
    loading,
    summary,
    error,
    saveName,
    setSaveName,
    saveDescription,
    setSaveDescription,
    saving,
    saveSuccess,
    saveError,
    model,
    setModel,
    submitSummarize,
    saveSummaryToProject,
  };
}
