import React from "react";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import ArtifactSelector from "../components/primitives/ArtifactSelector";
import MarkdownDisplay from "../components/primitives/MarkdownDisplay";
import PageHeading from "../components/primitives/PageHeading";
import useViewSummaryPage from "../components/summarize/useViewSummaryPage";
import "../styles/Home.css";

export default function ViewSummary() {
  const { available, selected, setSelected, selectedName, content, loading, error } =
    useViewSummaryPage();

  return (
    <div className="layout-page">
      <div className="layout-card layout-card--padded layout-card--full-width">
        <div className="layout-flex-col gap-sm" style={{ marginBottom: 16 }}>
          <ArtifactSelector
            items={available}
            selectedId={selected}
            onSelect={setSelected}
            listClassName="selector-strip"
            buttonClassName="selector-button"
            emptyMessage="No summaries available"
            wrapperStyle={{ width: "100%" }}
          />
          <div className="layout-space-between">
            <PageHeading
              as="h2"
              title={selectedName || "Select a summary"}
              className="heading-md"
            />
          </div>
          {loading ? <div className="alert alert--info">Loading...</div> : null}
          <ErrorDisplay message={error} type="error" variant="alert" />
          <MarkdownDisplay content={content} className="body-base text-primary" />
        </div>
      </div>
    </div>
  );
}
