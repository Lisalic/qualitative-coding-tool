import FormShell from "../forms/FormShell";
import Panel from "../shell/Panel";

/**
 * Step 1 of every editor: pick a source, name the output. Generalized
 * from `CodingSetupPanel.jsx`'s shape (source data & codebook on the
 * left, output naming on the right) -- the filter and codebook editors
 * now open into this same gate instead of starting straight in their
 * workspace with no equivalent step.
 *
 * `outputFields` may be omitted -- the codebook editor's Refine mode
 * names nothing, since it saves a new version of an existing artifact --
 * in which case the output panel isn't rendered at all rather than left
 * standing empty.
 */
export default function EditorSetupStep({
  sourceTitle = "Source",
  sourceFields,
  outputTitle = "Output",
  outputFields,
  onSubmit,
  submitLabel,
  submitLoadingLabel,
  submitDisabled,
  submitLoading = false,
  error,
}) {
  return (
    <FormShell
      columns
      onSubmit={onSubmit}
      submitButton={{
        text: submitLabel,
        loadingText: submitLoadingLabel,
        disabled: submitDisabled,
        loading: submitLoading,
      }}
      error={error}
    >
      <Panel title={sourceTitle} className="flex-1" scroll={false} bodyClassName="flex flex-col gap-3">
        {sourceFields}
      </Panel>
      {outputFields && (
        <Panel title={outputTitle} className="flex-1" scroll={false} bodyClassName="flex flex-col gap-3">
          {outputFields}
        </Panel>
      )}
    </FormShell>
  );
}
