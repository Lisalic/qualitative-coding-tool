import { useEffect, useState } from "react";
import { apiFetch, postFormAndPoll } from "../../api";

export default function useComparePageData({
  fileType,
  compareEndpoint,
  fieldAName,
  fieldBName,
  initialA = "",
  validationMessage,
  usesJobPolling = false,
}) {
  const [items, setItems] = useState([]);
  const [a, setA] = useState(initialA || "");
  const [b, setB] = useState("");
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState("");
  const [createdFile, setCreatedFile] = useState(null);
  const [error, setError] = useState("");
  const [model, setModel] = useState("");
  const [name, setName] = useState("");
  const [additionalPrompt, setAdditionalPrompt] = useState("");

  useEffect(() => {
    setA(initialA || "");
  }, [initialA]);

  useEffect(() => {
    let mounted = true;
    apiFetch(`/api/my-files/?file_type=${fileType}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!mounted || !data) return;
        const list = (data.projects || []).map((project) => ({
          value: project.schema_name,
          label: project.display_name || project.schema_name,
        }));
        setItems(list);
        if (initialA) {
          const availableForB = list.filter((item) => item.value !== initialA);
          if (availableForB.length > 0) {
            setB((previousValue) => previousValue || availableForB[0].value);
          }
        }
      })
      .catch(() => {});

    return () => {
      mounted = false;
    };
  }, [fileType, initialA]);

  const submitCompare = async (event) => {
    event.preventDefault();
    setComparison("");
    setCreatedFile(null);
    setError("");

    if (!a || !b) {
      setError(validationMessage);
      return;
    }

    if (!name.trim()) {
      setError("Enter a name for the comparison");
      return;
    }

    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) {
      setError("Set your API key in the navbar first");
      return;
    }

    const form = new FormData();
    form.append(fieldAName, a);
    form.append(fieldBName, b);
    form.append("api_key", apiKey);
    form.append("name", name.trim());
    if (model) form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());

    try {
      setLoading(true);

      if (usesJobPolling) {
        // Endpoint has been converted to the background-job pattern
        // (kicks off a job and returns 202 {job_id, status}) -- poll
        // /api/jobs/{id} until it resolves rather than blocking on the
        // initial request. The job also persists the comparison as a
        // File artifact directly (see `name` above), so `data.file` is
        // the created artifact -- no separate save step needed.
        const { ok, data, error: pollError } = await postFormAndPoll(
          compareEndpoint,
          form,
        );
        if (!ok) {
          setError(pollError || "Failed to compare");
        } else {
          setComparison(data?.comparison || "");
          setCreatedFile(data?.file || null);
        }
        return;
      }

      const response = await apiFetch(compareEndpoint, {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      const data = await response.json();
      if (data.error) {
        setError(data.error);
      } else {
        setComparison(data.comparison || "");
        setCreatedFile(data?.file || null);
      }
    } catch (submitError) {
      setError(String(submitError));
    } finally {
      setLoading(false);
    }
  };

  return {
    items,
    a,
    b,
    setA,
    setB,
    loading,
    comparison,
    createdFile,
    error,
    model,
    setModel,
    name,
    setName,
    additionalPrompt,
    setAdditionalPrompt,
    submitCompare,
  };
}
