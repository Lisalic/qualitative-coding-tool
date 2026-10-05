import { useEffect, useState } from "react";
import { apiFetch, postFormAndPoll, MISSING_API_KEY_MESSAGE } from "../../api";
import { useUnmountSignal } from "../primitives/useUnmountSignal";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";

export default function useSummarizeCodingPage() {
  const [codings, setCodings] = useState([]);
  const [selectedCoding, setSelectedCoding] = useState("");
  const [additionalPrompt, setAdditionalPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(null);
  // Leaving the page stops job polling (the job itself keeps running).
  const pollSignal = useUnmountSignal();
  const [partialWarning, setPartialWarning] = useState("");
  const [summary, setSummary] = useState("");
  const [createdFile, setCreatedFile] = useState(null);
  const [error, setError] = useState("");
  // Validation messages keyed by field, shown next to the field itself.
  const [fieldErrors, setFieldErrors] = useState({});
  const [listError, setListError] = useState("");
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  const [projects, setProjects] = useState([]);
  // Arriving from a project's Summaries tab preselects that project.
  const initialProjectId = useInitialProjectId();
  const [selectedProject, setSelectedProject] = useState(initialProjectId);

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
        // No silent preselection: summarizing is a paid run, so the coding
        // is always one the researcher actually chose (as on Compare).
        setCodings(list);
        setListError("");
      })
      .catch(() => {
        if (mounted) setListError("Couldn't load your codings. Check your connection and refresh.");
      });
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
    const nextFieldErrors = {};
    if (!selectedCoding) nextFieldErrors.coding = "Choose a coding to summarize.";
    if (!name.trim()) nextFieldErrors.name = "Enter a name for the summary.";
    if (!selectedProject) nextFieldErrors.project = "Choose a project.";
    if (!model) nextFieldErrors.model = "Choose an AI model.";
    setFieldErrors(nextFieldErrors);
    if (Object.keys(nextFieldErrors).length > 0) return;
    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) return setError(MISSING_API_KEY_MESSAGE);

    const form = new FormData();
    form.append("coding", selectedCoding);
    form.append("api_key", apiKey);
    form.append("name", name.trim());
    form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());
    form.append("project_id", selectedProject);

    try {
      setLoading(true);
      setProgress(null);
      // The job also persists the summary as a File artifact directly
      // (see `name` above), so `data.file` is the created artifact -- no
      // separate save step needed.
      const {
        ok,
        data,
        error: pollError,
        isPartial,
      } = await postFormAndPoll("/api/summarize-coding/", form, {
        onProgress: setProgress,
        signal: pollSignal(),
      });
      if (!ok) {
        setError(pollError || "The summary failed. Please try again.");
      } else {
        setSummary((data && data.summary) || "");
        setCreatedFile((data && data.file) || null);
        if (data?.partial) {
          const reason = data.partial_error
            ? `Stopped early: ${data.partial_error}`
            : "Try a paid model or a smaller input.";
          setPartialWarning(
            `Only ${data.batches_processed}/${data.batches_total} batches completed. ${reason}`,
          );
        } else if (isPartial) {
          setPartialWarning(
            `Only part of the summary finished${pollError ? ` (${pollError})` : ""}. What finished was saved.`,
          );
        }
      }
    } catch (submitError) {
      setError(submitError?.message || "The summary failed. Please try again.");
    } finally {
      setLoading(false);
      setProgress(null);
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
    fieldErrors,
    listError,
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
