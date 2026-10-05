import { pillRadioInput, pillRadioLabel } from "../../lib/uiClasses";

// Shared "which content types to sample" control for Filter Data,
// Generate Codebook, and Apply Codebook -- mirrors backend/app/api/
// schemas.py's ContentScope ("both" | "posts" | "comments") field these
// three tools now share. Options for a table with zero rows are disabled
// rather than hidden, so the control's shape stays consistent across
// databases.
const OPTIONS = [
  { value: "both", label: "Posts + Comments" },
  { value: "posts", label: "Posts only" },
  { value: "comments", label: "Comments only" },
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
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-sm">Content to sample</legend>
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
              className={pillRadioInput}
            />
            <label htmlFor={`${radioName}-${opt.value}`} className={pillRadioLabel}>
              {opt.label}
            </label>
          </div>
        ))}
      </div>
    </fieldset>
  );
}
