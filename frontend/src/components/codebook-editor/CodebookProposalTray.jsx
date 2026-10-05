import Panel from "../shell/Panel";
import DialogService from "../feedback/DialogService";
import { btnSm } from "../../lib/uiClasses";

const FIELDS = [
  ["definition", "Definition"],
  ["inclusion", "Inclusion"],
  ["exclusion", "Exclusion"],
  ["keywords", "Keywords"],
  ["example", "Example"],
];

/**
 * The review tray: codes the assistant proposed, none of them yet part of
 * the codebook.
 *
 * Every field the model produced is shown, because accepting a code is
 * accepting its definition and its inclusion/exclusion criteria -- a
 * name-only card would ask the researcher to approve text they never saw.
 * Dismiss is remembered rather than merely closing the card, so a later
 * run cannot re-offer the same code (see
 * `codebookEditorState.dismissProposal`).
 */
export default function CodebookProposalTray({
  proposals,
  onAccept,
  onDismiss,
  onAcceptAll,
  onDismissAll,
  disabled,
}) {
  // Dismissals are remembered (a later run won't re-offer them), so
  // dismissing a whole tray is worth a second look.
  const confirmDismissAll = async () => {
    const confirmed = await DialogService.confirm(
      `Dismiss all ${proposals.length} proposed codes? Dismissed proposals won't be offered again.`,
      { title: "Dismiss all", confirmLabel: "Dismiss all", danger: true },
    );
    if (confirmed) onDismissAll();
  };

  return (
    <Panel
      title={`Proposed codes (${proposals.length})`}
      actions={
        <>
          <button type="button" className={btnSm} onClick={confirmDismissAll} disabled={disabled}>
            Dismiss all
          </button>
          <button type="button" className={btnSm} onClick={onAcceptAll} disabled={disabled}>
            Accept all
          </button>
        </>
      }
      bodyClassName="flex flex-col gap-2"
    >
      {proposals.map((proposal) => (
        <article key={proposal.key} className="border border-line bg-surface-raised p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              {proposal.family_name ? (
                <div className="text-xs uppercase tracking-wide text-paper/50">
                  {proposal.family_name}
                </div>
              ) : null}
              <h3 className="truncate text-sm font-semibold" title={proposal.name}>
                {proposal.name}
              </h3>
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                className={btnSm}
                onClick={() => onDismiss(proposal.key)}
                disabled={disabled}
                aria-label={`Dismiss ${proposal.name}`}
              >
                Dismiss
              </button>
              <button
                type="button"
                className={btnSm}
                onClick={() => onAccept(proposal.key)}
                disabled={disabled}
                aria-label={`Accept ${proposal.name}`}
              >
                Accept
              </button>
            </div>
          </div>

          <dl className="mt-2 flex flex-col gap-1 text-xs">
            {FIELDS.map(([field, label]) =>
              proposal[field] ? (
                <div key={field} className="flex gap-2">
                  <dt className="w-24 shrink-0 text-paper/50">{label}</dt>
                  <dd className="min-w-0 text-paper/80">{proposal[field]}</dd>
                </div>
              ) : null,
            )}
          </dl>
        </article>
      ))}
    </Panel>
  );
}
