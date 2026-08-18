import MarkdownDisplay from "../primitives/MarkdownDisplay";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";

const smallBtn =
  "border border-paper px-3.5 py-2 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

export default function SummaryOutputSection({ summary, createdFile }) {
  if (summary === "") return null;

  return (
    <div className="mt-6 flex">
      <div className="w-full border-2 border-paper p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Summary result</h2>
          <div className="flex gap-2">
            <button
              type="button"
              className={smallBtn}
              onClick={() => {
                if (navigator.clipboard && summary) {
                  navigator.clipboard.writeText(summary).catch(() => {});
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
              viewPath="/summaryview"
              viewState={{ selectedSummary: createdFile.schema_name }}
            />
          </div>
        )}

        <div className="mt-3 max-h-[60vh] overflow-auto border border-paper bg-white/5 p-4 text-sm leading-relaxed text-paper">
          <MarkdownDisplay content={summary} />
        </div>
      </div>
    </div>
  );
}
