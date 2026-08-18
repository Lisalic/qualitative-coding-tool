import React from "react";
import ReactMarkdown from "react-markdown";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";

const smallBtn =
  "border border-paper px-3.5 py-2 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

export default function CompareResultPanel({
  comparison,
  createdFile,
  viewPath,
  viewStateKey,
}) {
  if (comparison === "") return null;

  return (
    <div className="mt-6 flex">
      <div className="w-full border-2 border-paper p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Comparison result</h2>
          <div className="flex gap-2">
            <button
              type="button"
              className={smallBtn}
              onClick={() => {
                if (navigator.clipboard && comparison) {
                  navigator.clipboard.writeText(comparison).catch(() => {});
                }
              }}
            >
              Copy
            </button>
          </div>
        </div>

        {createdFile && (
          <div className="mb-3">
            <ArtifactCreatedMessage
              name={createdFile.filename}
              viewPath={viewPath}
              viewState={{ [viewStateKey]: createdFile.schema_name }}
            />
          </div>
        )}

        <div className="mt-3 max-h-[60vh] overflow-auto border border-paper bg-white/5 p-4 text-sm leading-relaxed text-paper">
          <ReactMarkdown>{comparison}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
