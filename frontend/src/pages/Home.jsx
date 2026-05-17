import { useNavigate } from "react-router-dom";
import ProjectsListSection from "../components/project/ProjectsListSection";
import CreateProjectSection from "../components/project/CreateProjectSection";
import useHomePage from "../components/project/useHomePage";
import "../styles/Home.css";

export default function Home() {
  const page = useHomePage();
  const navigate = useNavigate();

  return (
    <div className="layout-page">
      <div className="layout-card layout-card--padded layout-card--full-width">
        <ProjectsListSection
          projects={page.projects}
          loading={page.loading}
          error={page.error}
          onViewProject={(projectId) => navigate(`/project/${projectId}`)}
        />
        <CreateProjectSection
          showForm={page.showForm}
          name={page.name}
          description={page.description}
          message={page.message}
          onCreateClick={page.handleCreateClick}
          onNameChange={page.setName}
          onDescriptionChange={page.setDescription}
          onSubmit={page.handleCreateProject}
          onCancel={page.handleCancel}
        />
      </div>
    </div>
  );
}
