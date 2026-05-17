import React from "react";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import SummarizeRequestSection from "../components/summarize/SummarizeRequestSection";
import SummaryOutputSection from "../components/summarize/SummaryOutputSection";
import PageHeading from "../components/primitives/PageHeading";
import useSummarizeCodingPage from "../components/summarize/useSummarizeCodingPage";
import "../styles/Home.css";

export default function SummarizeCoding() {
  const {
    codings,
    selectedCoding,
    setSelectedCoding,
    projects,
    selectedProject,
    setSelectedProject,
    additionalPrompt,
    setAdditionalPrompt,
    loading,
    summary,
    error,
    saveName,
    setSaveName,
    saveDescription,
    setSaveDescription,
    saving,
    saveSuccess,
    saveError,
    model,
    setModel,
    submitSummarize,
    saveSummaryToProject,
  } = useSummarizeCodingPage();

  return (
    <div className="home-container">
      <div style={{ width: "100%", maxWidth: 1400, padding: 20 }}>
        <PageHeading title="Summarize Coding" style={{ textAlign: "center" }} />
        <SummarizeRequestSection
          codings={codings}
          selectedCoding={selectedCoding}
          onCodingChange={setSelectedCoding}
          model={model}
          onModelChange={setModel}
          additionalPrompt={additionalPrompt}
          onAdditionalPromptChange={setAdditionalPrompt}
          loading={loading}
          onSubmit={submitSummarize}
        />
        <ErrorDisplay message={error} variant="message" />
        <SummaryOutputSection
          summary={summary}
          projects={projects}
          selectedProject={selectedProject}
          onProjectChange={setSelectedProject}
          saveName={saveName}
          onSaveNameChange={setSaveName}
          saveDescription={saveDescription}
          onSaveDescriptionChange={setSaveDescription}
          onSave={saveSummaryToProject}
          saving={saving}
          saveSuccess={saveSuccess}
          saveError={saveError}
        />
      </div>
    </div>
  );
}
