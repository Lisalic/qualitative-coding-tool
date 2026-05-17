import { useEffect, useMemo } from "react";
import { useLocation } from "react-router-dom";
import useProjectScopedFiles from "./useProjectScopedFiles";

const MODE_CONFIG = {
  raw: {
    fileType: "raw_data",
    containerClassName: "data-container",
    cardClassName: "",
    selection: {
      wrapperClassName: "",
      selectClassName: "",
      listClassName: "database-selector",
      buttonClassName: "db-button",
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
    containerClassName: "layout-page",
    cardClassName: "layout-card layout-card--padded",
    selection: {
      wrapperClassName: "body-base",
      selectClassName: "form__input",
      listClassName: "selector-strip",
      buttonClassName: "selector-button",
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
    containerClassName: config.containerClassName,
    cardClassName: config.cardClassName,
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
