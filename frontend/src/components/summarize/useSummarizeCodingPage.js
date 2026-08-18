import { useEffect, useState } from "react";
import { apiFetch, postFormAndPoll } from "../../api";

export default function useSummarizeCodingPage() {
  const [codings, setCodings] = useState([]);
  const [selectedCoding, setSelectedCoding] = useState("");
  const [additionalPrompt, setAdditionalPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState("");
  const [createdFile, setCreatedFile] = useState(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
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

  const submitSummarize = async (event) => {
    event.preventDefault();
    setSummary("");
    setCreatedFile(null);
    setError("");
    if (!selectedCoding) return setError("Select a coding to summarize");
    if (!name.trim()) return setError("Enter a name for the summary");
    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) return setError("Set your API key in the navbar first");

    const form = new FormData();
    form.append("coding", selectedCoding);
    form.append("api_key", apiKey);
    form.append("name", name.trim());
    if (model) form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());

    try {
      setLoading(true);
      // The job also persists the summary as a File artifact directly
      // (see `name` above), so `data.file` is the created artifact -- no
      // separate save step needed.
      const { ok, data, error: pollError } = await postFormAndPoll("/api/summarize-coding/", form);
      if (!ok) {
        setError(pollError || "Failed to generate summary");
      } else {
        setSummary((data && data.summary) || "");
        setCreatedFile((data && data.file) || null);
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
    summary,
    createdFile,
    error,
    name,
    setName,
    model,
    setModel,
    submitSummarize,
  };
}
