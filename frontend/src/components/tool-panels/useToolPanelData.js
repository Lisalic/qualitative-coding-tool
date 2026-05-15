import { useEffect, useState } from "react";
import { apiFetch } from "../../api";

const mapFileOptions = (payload) =>
  (payload?.projects || []).map((project) => ({
    value: project.schema_name,
    label: project.display_name || project.schema_name,
    meta: project,
  }));

export function useToolPanelData({ includeCodebooks = false } = {}) {
  const [databases, setDatabases] = useState([]);
  const [filteredDatabases, setFilteredDatabases] = useState([]);
  const [projects, setProjects] = useState([]);
  const [codebooks, setCodebooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const requests = [
          apiFetch("/api/my-files/?file_type=raw_data"),
          apiFetch("/api/my-files/?file_type=filtered_data"),
          apiFetch("/api/projects/"),
        ];
        if (includeCodebooks) {
          requests.push(apiFetch("/api/list-codebooks"));
        }

        const responses = await Promise.all(requests);
        if (!mounted) return;

        const [rawResp, filteredResp, projectsResp, codebooksResp] = responses;

        if (rawResp.ok) {
          const rawData = await rawResp.json();
          if (!mounted) return;
          setDatabases(mapFileOptions(rawData));
        } else {
          setDatabases([]);
        }

        if (filteredResp.ok) {
          const filteredData = await filteredResp.json();
          if (!mounted) return;
          setFilteredDatabases(mapFileOptions(filteredData));
        } else {
          setFilteredDatabases([]);
        }

        if (projectsResp.ok) {
          const projectsData = await projectsResp.json();
          if (!mounted) return;
          setProjects(projectsData.projects || []);
        } else {
          setProjects([]);
        }

        if (includeCodebooks && codebooksResp) {
          if (codebooksResp.ok) {
            const codebookData = await codebooksResp.json();
            if (!mounted) return;
            setCodebooks(codebookData.codebooks || []);
          } else {
            setCodebooks([]);
          }
        } else {
          setCodebooks([]);
        }
      } catch (err) {
        if (!mounted) return;
        setError(err?.message || "Failed to load panel data");
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();
    return () => {
      mounted = false;
    };
  }, [includeCodebooks]);

  return {
    databases,
    filteredDatabases,
    projects,
    codebooks,
    loading,
    error,
  };
}
