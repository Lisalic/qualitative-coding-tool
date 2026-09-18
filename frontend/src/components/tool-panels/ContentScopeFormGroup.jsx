// Shared "which content types to sample" control for Filter Data,
// Generate Codebook, and Apply Codebook -- mirrors backend/app/api/
// schemas.py's ContentScope ("both" | "posts" | "comments") field these
// three tools now share. Options for a table with zero rows are disabled
// rather than hidden, so the control's shape stays consistent across
// databases.
const OPTIONS = [
  { value: "both", label: "Posts + Comments" },
  { value: "posts", label: "Posts Only" },
  { value: "comments", label: "Comments Only" },
];

export default function ContentScopeFormGroup({
  contentScope,
  onContentScopeChange,
  postsAvailable = true,
  commentsAvailable = true,
  disabled,
  radioName = "contentScope",
}) {
  const isDisabled = (value) => {
    if (disabled) return true;
    if (value === "posts") return !postsAvailable;
    if (value === "comments") return !commentsAvailable;
    return !postsAvailable && !commentsAvailable;
  };

  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm">Content to Sample</label>
      <div className="flex w-full gap-2">
        {OPTIONS.map((opt) => (
          <div key={opt.value} className="flex-1">
            <input
              type="radio"
              id={`${radioName}-${opt.value}`}
              name={radioName}
              value={opt.value}
              checked={contentScope === opt.value}
              onChange={() => onContentScopeChange(opt.value)}
              disabled={isDisabled(opt.value)}
              className="peer hidden"
            />
            <label
              htmlFor={`${radioName}-${opt.value}`}
              className="block cursor-pointer border border-paper px-3 py-2 text-center text-sm transition-colors hover:bg-paper hover:text-ink peer-checked:bg-paper peer-checked:text-ink peer-disabled:cursor-not-allowed peer-disabled:opacity-40 peer-disabled:hover:bg-transparent peer-disabled:hover:text-paper"
            >
              {opt.label}
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}
