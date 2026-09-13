import React from "react";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";

export default function CompareResultPanel({
  comparison,
  createdFile,
  viewPath,
  viewStateKey,
}) {
  if (comparison === "" || !createdFile) return null;

  return (
    <div className="mt-4">
      <ArtifactCreatedMessage
        name={createdFile.filename}
        viewPath={viewPath}
        viewState={{ [viewStateKey]: createdFile.schema_name }}
      />
    </div>
  );
}
