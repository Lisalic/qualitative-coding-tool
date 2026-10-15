import ProjectsListSection from "../features/projects/ProjectsListSection";
import CreateProjectSection from "../features/projects/CreateProjectSection";
import useHomePage from "../features/projects/useHomePage";
import PageShell from "../components/layout/PageShell";

export default function Home() {
  const page = useHomePage();

  return (
    <PageShell title="Projects" width="wide" bodyClassName="flex flex-col gap-3">
      <ProjectsListSection
        projects={page.projects}
        loading={page.loading}
        error={page.error}
      />
      <CreateProjectSection
        showForm={page.showForm}
        name={page.name}
        description={page.description}
        message={page.message}
        messageIsError={page.messageIsError}
        creating={page.creating}
        onCreateClick={page.handleCreateClick}
        onNameChange={page.setName}
        onDescriptionChange={page.setDescription}
        onSubmit={page.handleCreateProject}
        onCancel={page.handleCancel}
      />
    </PageShell>
  );
}
