import React from "react";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import ProgressBar from "../components/feedback/ProgressBar";
import SummarizeRequestSection from "../features/summarize/SummarizeRequestSection";
import SummaryOutputSection from "../features/summarize/SummaryOutputSection";
import PageShell from "../components/layout/PageShell";
import useSummarizeCodingPage from "../features/summarize/useSummarizeCodingPage";

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
    fieldErrors,
    listError,
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
        errors={fieldErrors}
      />
      <ErrorDisplay message={listError} variant="alert" />
      <ErrorDisplay message={error} variant="alert" />
      {loading && progress && (
        <ProgressBar current={progress.current} total={progress.total} label={progress.label} />
      )}
      {partialWarning && (
        <div role="status" className="border border-line bg-surface-raised px-3 py-2 text-center text-sm text-paper">
          {partialWarning}
        </div>
      )}
      <SummaryOutputSection summary={summary} createdFile={createdFile} partial={Boolean(partialWarning)} />
    </PageShell>
  );
}
