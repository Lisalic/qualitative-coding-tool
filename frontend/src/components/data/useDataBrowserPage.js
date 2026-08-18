import { useEffect, useMemo } from "react";
import { useLocation } from "react-router-dom";
import useProjectScopedFiles from "./useProjectScopedFiles";

const SELECT_CLASSES =
  "border border-paper bg-white/5 px-3 py-2 text-paper focus:outline-none focus:ring-2 focus:ring-paper";

const MODE_CONFIG = {
  raw: {
    fileType: "raw_data",
    selection: {
      wrapperClassName: "mb-4 flex items-center gap-2",
      selectClassName: SELECT_CLASSES,
      listClassName: "mb-6 flex flex-wrap gap-2.5 border-2 border-paper p-4",
      buttonClassName:
        "border border-paper px-4 py-2.5 text-sm transition-colors hover:bg-paper hover:text-ink",
      noProjectFilesMessage: "No raw files in project",
      noDatabaseMessage: "No databases available",
    },
    table: {
      isFilteredView: false,
      emptyMessage: "Select a database to view raw data",
    },
  },
  filtered: {
    fileType: "filtered_data",
    selection: {
      wrapperClassName: "mb-4 flex items-center gap-2",
      selectClassName: SELECT_CLASSES,
      listClassName: "mb-6 flex flex-wrap gap-2.5 border-2 border-paper p-4",
      buttonClassName:
        "border border-paper px-4 py-2.5 text-sm transition-colors hover:bg-paper hover:text-ink",
      noProjectFilesMessage: "No filtered files in project",
      noDatabaseMessage: "No filtered databases available",
    },
    table: {
      isFilteredView: true,
      emptyMessage: "Select a project file to view filtered data",
    },
  },
};

export default function useDataBrowserPage({ mode = "raw" } = {}) {
  const location = useLocation();
  const config = MODE_CONFIG[mode] || MODE_CONFIG.raw;
  const scoped = useProjectScopedFiles(config.fileType);

  useEffect(() => {
    if (!location.state?.selectedDatabase) return;
    const selected = location.state.selectedDatabase;
    const selectedId =
      typeof selected === "string" ? selected : selected?.name || selected?.id || "";
    scoped.setSelectedDatabase(selectedId);
  }, [location.state, scoped.setSelectedDatabase]);

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
    selectionProps: config.selection,
    tableProps: config.table,
  };
}
