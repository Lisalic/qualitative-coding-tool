import { useLocation } from "react-router-dom";

export function useInitialProjectId() {
  const location = useLocation();
  const projectId = location?.state?.projectId;
  return projectId != null ? String(projectId) : "";
}
