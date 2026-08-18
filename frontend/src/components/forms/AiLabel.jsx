import React from "react";

const ICON_PATH =
  "M12 2.9c.34 0 .64.23.73.56l1.18 4.34c.14.52.55.93 1.07 1.07l4.34 1.18a.76.76 0 0 1 0 1.46l-4.34 1.18c-.52.14-.93.55-1.07 1.07l-1.18 4.34a.76.76 0 0 1-1.46 0l-1.18-4.34a1.58 1.58 0 0 0-1.07-1.07l-4.34-1.18a.76.76 0 0 1 0-1.46l4.34-1.18c.52-.14.93-.55 1.07-1.07l1.18-4.34c.09-.33.39-.56.73-.56z";

export default function AiLabel({
  text,
  htmlFor,
  className = "",
  style,
  as = "label",
  title = "AI-use involved",
}) {
  const Tag = as;
  const tagProps = { className, style };
  if (Tag === "label" && htmlFor) {
    tagProps.htmlFor = htmlFor;
  }

  return (
    <Tag {...tagProps}>
      <span className="inline-flex items-center gap-1.5 text-sm">
        <span>{text}</span>
        <span className="group relative inline-flex cursor-help items-center">
          <svg
            className="h-3.5 w-3.5 fill-current text-paper/70"
            viewBox="0 0 24 24"
            width="14"
            height="14"
            aria-hidden="true"
            focusable="false"
          >
            <path d={ICON_PATH} />
          </svg>
          <span
            role="tooltip"
            className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 -translate-x-1/2 translate-y-1 whitespace-nowrap border border-paper bg-ink px-2 py-1 text-xs text-paper opacity-0 transition-all group-hover:translate-y-0 group-hover:opacity-100"
          >
            {title}
          </span>
        </span>
        <span className="sr-only">{title}</span>
      </span>
    </Tag>
  );
}
