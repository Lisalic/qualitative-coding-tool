import React from "react";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import SummarizeRequestSection from "../components/summarize/SummarizeRequestSection";
import SummaryOutputSection from "../components/summarize/SummaryOutputSection";
import PageHeading from "../components/primitives/PageHeading";
import useSummarizeCodingPage from "../components/summarize/useSummarizeCodingPage";

export default function SummarizeCoding() {
  const {
    codings,
    selectedCoding,
    setSelectedCoding,
    additionalPrompt,
    setAdditionalPrompt,
    loading,
    summary,
    createdFile,
    error,
    name,
    setName,
    model,
    setModel,
    submitSummarize,
  } = useSummarizeCodingPage();

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <PageHeading title="Summarize Coding" className="mb-6 text-center text-2xl font-bold" />
      <SummarizeRequestSection
        codings={codings}
        selectedCoding={selectedCoding}
        onCodingChange={setSelectedCoding}
        model={model}
        onModelChange={setModel}
        name={name}
        onNameChange={setName}
        additionalPrompt={additionalPrompt}
        onAdditionalPromptChange={setAdditionalPrompt}
        loading={loading}
        onSubmit={submitSummarize}
      />
      <div className="mt-4">
        <ErrorDisplay message={error} variant="message" />
      </div>
      <SummaryOutputSection summary={summary} createdFile={createdFile} />
    </div>
  );
}
