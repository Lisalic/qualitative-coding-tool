import React from "react";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import ProgressBar from "../components/feedback/ProgressBar";
import SummarizeRequestSection from "../components/summarize/SummarizeRequestSection";
import SummaryOutputSection from "../components/summarize/SummaryOutputSection";
import PageShell from "../components/shell/PageShell";
import useSummarizeCodingPage from "../components/summarize/useSummarizeCodingPage";

export default function SummarizeCoding() {
  const {
    codings,
    selectedCoding,
    setSelectedCoding,
    additionalPrompt,
    setAdditionalPrompt,
    loading,
    progress,
    partialWarning,
    summary,
    createdFile,
    error,
    name,
    setName,
    model,
    setModel,
    projects,
    selectedProject,
    setSelectedProject,
    submitSummarize,
  } = useSummarizeCodingPage();

  return (
    <PageShell title="Summarize Coding" width="wide" bodyClassName="flex flex-col gap-3">
      <SummarizeRequestSection
        codings={codings}
        selectedCoding={selectedCoding}
        onCodingChange={setSelectedCoding}
        model={model}
        onModelChange={setModel}
        name={name}
        onNameChange={setName}
        projects={projects}
        selectedProject={selectedProject}
        onProjectChange={setSelectedProject}
        additionalPrompt={additionalPrompt}
        onAdditionalPromptChange={setAdditionalPrompt}
        loading={loading}
        onSubmit={submitSummarize}
      />
      <ErrorDisplay message={error} variant="message" />
      {loading && progress && (
        <ProgressBar current={progress.current} total={progress.total} label={progress.label} />
      )}
      {partialWarning && (
        <div className="border border-paper bg-surface-raised px-3 py-2 text-center text-sm text-paper">
          {partialWarning}
        </div>
      )}
      <SummaryOutputSection summary={summary} createdFile={createdFile} />
    </PageShell>
  );
}
