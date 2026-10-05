import { useEffect, useState } from "react";
import { apiFetch, postFormAndPoll, MISSING_API_KEY_MESSAGE } from "../../api";
import { useUnmountSignal } from "../primitives/useUnmountSignal";

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
  const [createdFile, setCreatedFile] = useState(null);
  const [error, setError] = useState("");
  // Validation messages keyed by field, shown next to the field itself.
  const [fieldErrors, setFieldErrors] = useState({});
  const [progress, setProgress] = useState(null);
  const [partialNote, setPartialNote] = useState("");
  const [listError, setListError] = useState("");
  // Leaving the page stops job polling (the job itself keeps running).
  const pollSignal = useUnmountSignal();
  const [model, setModel] = useState("");
  const [name, setName] = useState("");
  const [additionalPrompt, setAdditionalPrompt] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");

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
        setListError("");
        if (initialA) {
          const availableForB = list.filter((item) => item.value !== initialA);
          if (availableForB.length > 0) {
            setB((previousValue) => previousValue || availableForB[0].value);
          }
        }
      })
      .catch(() => {
        if (mounted) setListError("Couldn't load the files to compare. Check your connection and refresh.");
      });

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
        setProjects(data.projects || []);
      })
      .catch(() => {});

    return () => {
      mounted = false;
    };
  }, []);

  const handleSwap = () => {
    const tempA = a;
    setA(b);
    setB(tempA);
  };

  const submitCompare = async (event) => {
    event.preventDefault();
    setComparison("");
    setCreatedFile(null);
    setError("");
    setPartialNote("");

    const nextFieldErrors = {};
    if (!a) nextFieldErrors.a = validationMessage;
    if (!b) nextFieldErrors.b = validationMessage;
    if (a && b && a === b) nextFieldErrors.b = "Pick a different file from A.";
    if (!name.trim()) nextFieldErrors.name = "Enter a name for the comparison.";
    if (!selectedProject) nextFieldErrors.project = "Choose a project.";
    if (!model) nextFieldErrors.model = "Choose an AI model.";
    setFieldErrors(nextFieldErrors);
    if (Object.keys(nextFieldErrors).length > 0) return;

    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) {
      setError(MISSING_API_KEY_MESSAGE);
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
      setProgress(null);

      const {
        ok,
        data,
        error: pollError,
        isPartial,
      } = await postFormAndPoll(compareEndpoint, form, { signal: pollSignal(), onProgress: setProgress });
      if (!ok) {
        setError(pollError || "The comparison failed. Please try again.");
      } else {
        setComparison((data && data.comparison) || "");
        setCreatedFile((data && data.file) || null);
        if (isPartial) {
          setPartialNote(
            `Only part of the comparison finished${pollError ? ` (${pollError})` : ""}. What finished was saved.`,
          );
        }
      }
    } catch (err) {
      setError(err?.message || "The comparison failed. Please try again.");
    } finally {
      setLoading(false);
      setProgress(null);
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
    fieldErrors,
    progress,
    partialNote,
    listError,
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
    handleSwap,
  };
}
