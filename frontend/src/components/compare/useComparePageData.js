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
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");

  // Computed deterministic comparison states (QC-002)
  const [computedData, setComputedData] = useState(null);
  const [computedLoading, setComputedLoading] = useState(false);
  const [computedError, setComputedError] = useState("");

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

  // Automatically compute deterministic comparison when both A and B are selected
  useEffect(() => {
    if (!a || !b) {
      setComputedData(null);
      setComputedError("");
      return;
    }

    let mounted = true;
    setComputedLoading(true);
    setComputedError("");

    const endpoint =
      fileType === "coding"
        ? `/api/comparison/codings?file_a=${encodeURIComponent(a)}&file_b=${encodeURIComponent(b)}`
        : `/api/comparison/codebooks?file_a=${encodeURIComponent(a)}&file_b=${encodeURIComponent(b)}`;

    apiFetch(endpoint)
      .then(async (res) => {
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || errData.error || "Failed to compute comparison");
        }
        return res.json();
      })
      .then((data) => {
        if (mounted) {
          setComputedData(data);
          setComputedLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setComputedError(err.message);
          setComputedLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [a, b, fileType]);

  const handleSwap = () => {
    const tempA = a;
    setA(b);
    setB(tempA);
  };

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

    if (!selectedProject) {
      setError("Select a project");
      return;
    }

    if (!model) {
      setError("Select an AI model");
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
    form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());
    form.append("project_id", selectedProject);

    try {
      setLoading(true);

      if (usesJobPolling) {
        const data = await postFormAndPoll(compareEndpoint, form);
        setComparison(data.comparison || "");
        setCreatedFile(data.file || null);
      } else {
        const response = await apiFetch(compareEndpoint, {
          method: "POST",
          body: form,
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || errorData.detail || "Comparison failed");
        }

        const data = await response.json();
        setComparison(data.comparison);
      }
    } catch (err) {
      setError(err.message);
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
    projects,
    selectedProject,
    setSelectedProject,
    submitCompare,
    computedData,
    computedLoading,
    computedError,
    handleSwap,
  };
}
