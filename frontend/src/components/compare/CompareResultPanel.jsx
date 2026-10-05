import React from "react";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";

export default function CompareResultPanel({
  comparison,
  createdFile,
  viewPath,
  viewStateKey,
  partialNote = "",
}) {
  if (comparison === "" || !createdFile) return null;

  return (
    <div>
      <ArtifactCreatedMessage
        name={createdFile.filename}
        viewPath={viewPath}
        viewState={{ [viewStateKey]: createdFile.schema_name }}
        neutral={Boolean(partialNote)}
        note={partialNote}
      />
    </div>
  );
}
