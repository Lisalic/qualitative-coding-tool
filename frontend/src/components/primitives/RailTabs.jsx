/**
 * Underlined tab strip for a right-rail `Panel` title -- the mode switch
 * shared by View Coding's rail (Codebook / AI Coding / Coverage) and the
 * integrate workspace's rail (Code / Comparison). `tabs` is
 * `[{ value, label, count }]`; a positive `count` renders as a compact
 * badge. Wraps rather than clipping when the rail is narrow.
 */
export default function RailTabs({ tabs, activeTab, onChange }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1" role="tablist">
      {tabs.map(({ value, label, count }) => {
        const isActive = value === activeTab;
        return (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`border-b-2 pb-0.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
              isActive ? "border-paper text-paper" : "border-transparent text-paper/50 hover:text-paper"
            }`}
            onClick={() => onChange(value)}
          >
            {label}
            {count > 0 && (
              <span className="ml-1 bg-paper px-1 text-[10px] font-semibold tracking-normal text-ink">{count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
