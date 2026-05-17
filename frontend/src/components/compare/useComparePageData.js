import { useEffect, useState } from "react";
import { apiFetch } from "../../api";

export default function useComparePageData({
  fileType,
  compareEndpoint,
  fieldAName,
  fieldBName,
  initialA = "",
  validationMessage,
}) {
  const [items, setItems] = useState([]);
  const [a, setA] = useState(initialA || "");
  const [b, setB] = useState("");
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState("");
  const [error, setError] = useState("");
  const [model, setModel] = useState("");
  const [projects, setProjects] = useState([]);
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

  const submitCompare = async (event) => {
    event.preventDefault();
    setComparison("");
    setError("");

    if (!a || !b) {
      setError(validationMessage);
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
    if (model) form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());

    try {
      setLoading(true);
      const response = await apiFetch(compareEndpoint, {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `HTTP ${response.status}`);
      }
      const data = await response.json();
      if (data.error) setError(data.error);
      else setComparison(data.comparison || "");
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
    error,
    model,
    setModel,
    projects,
    additionalPrompt,
    setAdditionalPrompt,
    submitCompare,
  };
}
