import { useEffect, useMemo } from "react";
import { useLocation } from "react-router-dom";
import useProjectScopedFiles from "./useProjectScopedFiles";
import { useRefParam } from "../primitives/useRefParam";

const MODE_CONFIG = {
  raw: {
    fileType: "raw_data",
    selection: {
      noProjectFilesMessage: "No raw files in project",
      noDatabaseMessage: "No databases available",
    },
    table: {
      isFilteredView: false,
      emptyMessage: "Select a database to view its rows",
    },
  },
  filtered: {
    fileType: "filtered_data",
    selection: {
      noProjectFilesMessage: "No filtered files in project",
      noDatabaseMessage: "No filtered databases available",
    },
    table: {
      isFilteredView: true,
      emptyMessage: "Select a database to view its rows",
    },
  },
};

export default function useDataBrowserPage({ mode = "raw" } = {}) {
  const location = useLocation();
  const config = MODE_CONFIG[mode] || MODE_CONFIG.raw;
  const scoped = useProjectScopedFiles(config.fileType);
  const { setSelectedDatabase } = scoped;
  // The open database lives in the URL as `?ref=` so refresh and Back keep
  // it; a link's `location.state.selectedDatabase` still wins.
  const urlRef = useRefParam(scoped.selectedDatabase);

  useEffect(() => {
    const selected = location.state?.selectedDatabase || urlRef;
    if (!selected) return;
    const selectedId =
      typeof selected === "string" ? selected : selected?.name || selected?.id || "";
    setSelectedDatabase((prev) => (prev === selectedId ? prev : selectedId));
  }, [location.state, urlRef, setSelectedDatabase]);

  const projects = useMemo(
    () => (scoped.projectsList.length > 0 ? scoped.projectsList : scoped.userProjects || []),
    [scoped.projectsList, scoped.userProjects],
  );

  const useProjectFileList = Boolean(
    scoped.selectedProject && scoped.projectSource.length > 0,
  );

  return {
    mode,
    isFilteredView: config.table.isFilteredView,
    projects,
    selectedProject: scoped.selectedProject,
    setSelectedProject: scoped.setSelectedProject,
    selectedDatabase: scoped.selectedDatabase,
    setSelectedDatabase: scoped.setSelectedDatabase,
    projectFiles: scoped.projectFiles,
    fallbackItems: scoped.fallbackItems,
    useProjectFileList,
    selectedMetadata: scoped.selectedMetadata,
    selectedDescription: scoped.selectedDescription,
    title: scoped.getTitle(),
    displayName: scoped.getDisplayName(),
    listError: scoped.listError,
    listLoading: scoped.listLoading,
    selectionProps: config.selection,
    tableProps: config.table,
  };
}
