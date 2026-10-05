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
 * The review tray for merged-code proposals -- same card shape as
 * `CodebookProposalTray`, plus a "Merged from" block: the whole point of
 * reviewing a merge is seeing which source codes fed it, not just the
 * result.
 *
 * A proposal whose sources all failed server-side verification
 * (`codebook_service._verify_proposal_sources`) still renders, with an
 * explicit "no matching source code" line rather than a silently empty
 * list -- an unverifiable merge is exactly the case where the
 * researcher's judgment matters most.
 */
export default function IntegrateProposalTray({
  proposals,
  codebookNames,
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
      `Dismiss all ${proposals.length} proposed merges? Dismissed proposals won't be offered again.`,
      { title: "Dismiss all", confirmLabel: "Dismiss all", danger: true },
    );
    if (confirmed) onDismissAll();
  };

  return (
    <Panel
      title={`Proposed merges (${proposals.length})`}
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

          <div className="mt-2 text-xs">
            <div className="text-paper/50">Merged from</div>
            {proposal.sources.length > 0 ? (
              <ul className="mt-0.5 flex flex-col gap-0.5">
                {proposal.sources.map((source, i) => (
                  <li key={i} className="text-paper/80">
                    {codebookNames[source.codebook] || source.codebook}
                    {source.family_name ? ` · ${source.family_name}` : ""} · {source.name}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-0.5 italic text-paper/50">
                No matching source code -- the assistant may have invented this.
              </p>
            )}
            {proposal.sources.length > 1 && proposal.rationale ? (
              <p className="mt-1 text-paper/70">{proposal.rationale}</p>
            ) : null}
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
