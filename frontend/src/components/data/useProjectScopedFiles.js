import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../api";

function normalizeDatabaseProjects(projects = []) {
  return projects.map((project) => {
    const tables = project.tables || [];
    const submissionsTable = tables.find((table) => table.table_name === "submissions");
    const commentsTable = tables.find((table) => table.table_name === "comments");
    return {
      name: project.schema_name,
      display_name: project.display_name,
      description: project.description ?? null,
      metadata: {
        created_at: project.created_at || null,
        tables,
        total_submissions: submissionsTable ? submissionsTable.row_count : 0,
        total_comments: commentsTable ? commentsTable.row_count : 0,
      },
    };
  });
}

export default function useProjectScopedFiles(fileType) {
  const [databases, setDatabases] = useState([]);
  const [userProjects, setUserProjects] = useState([]);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [selectedDatabase, setSelectedDatabase] = useState("");

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const resp = await apiFetch("/api/projects/");
        if (!resp.ok) return;
        const data = await resp.json();
        setProjectsList(Array.isArray(data.projects) ? data.projects : []);
      } catch (error) {
        console.error("Error fetching projects:", error);
      }
    };

    fetchProjects();
  }, []);

  useEffect(() => {
    const fetchDatabases = async () => {
      try {
        const meResp = await apiFetch("/api/me/");
        if (meResp.ok) {
          const projResp = await apiFetch(`/api/my-files/?file_type=${fileType}`);
          if (!projResp.ok) throw new Error("Failed to fetch user projects");
          const projData = await projResp.json();
          const projects = projData.projects || [];
          setUserProjects(projects);
          setDatabases(normalizeDatabaseProjects(projects));
          return;
        }

        const fallbackResp = await apiFetch(`/api/my-files/?file_type=${fileType}`);
        if (!fallbackResp.ok) return;
        const fallbackData = await fallbackResp.json();
        const projects = fallbackData.projects || [];
        setUserProjects(projects);
        setDatabases(normalizeDatabaseProjects(projects));
      } catch (error) {
        console.error("Error fetching scoped files:", error);
      }
    };

    fetchDatabases();
  }, [fileType]);

  const projectSource = useMemo(
    () => (projectsList.length > 0 ? projectsList : userProjects || []),
    [projectsList, userProjects],
  );

  const projectFiles = useMemo(() => {
    if (!selectedProject) return [];
    const projectObj = projectSource.find(
      (project) => String(project.id) === String(selectedProject),
    );
    return ((projectObj && projectObj.files) || [])
      .filter((file) => file.file_type === fileType)
      .map((file) => ({
        id: file.schema_name || file.id,
        name: file.display_name || file.schema_name || file.id,
      }));
  }, [fileType, projectSource, selectedProject]);

  const fallbackItems = useMemo(
    () =>
      (databases || []).map((database) => {
        const id = typeof database === "string" ? database : database.name || "";
        const found = (userProjects || []).find((project) => project.schema_name === id);
        const display = found?.display_name || database.display_name || id.replace(".db", "");
        return { id, name: display };
      }),
    [databases, userProjects],
  );

  const selectedDatabaseObj = useMemo(() => {
    const id = String(selectedDatabase || "").replace(".db", "");
    return (databases || []).find((database) => database && database.name === id);
  }, [databases, selectedDatabase]);

  const getTitle = () => {
    if (!selectedDatabase) return "Select a Database";
    const baseName = String(selectedDatabase).replace(".db", "");
    return `Database: ${selectedDatabaseObj?.display_name || baseName}`;
  };

  const getDisplayName = () => selectedDatabaseObj?.display_name || null;

  return {
    databases,
    userProjects,
    projectsList,
    selectedProject,
    setSelectedProject,
    selectedDatabase,
    setSelectedDatabase,
    projectFiles,
    fallbackItems,
    projectSource,
    selectedMetadata: selectedDatabaseObj?.metadata,
    selectedDescription: selectedDatabaseObj?.description,
    getTitle,
    getDisplayName,
  };
}
