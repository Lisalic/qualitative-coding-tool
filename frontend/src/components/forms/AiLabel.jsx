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
      <span className="ai-label">
        <span>{text}</span>
        <span className="ai-label__icon-wrap" data-tooltip={title}>
          <svg
            className="ai-label__icon"
            viewBox="0 0 24 24"
            width="14"
            height="14"
            aria-hidden="true"
            focusable="false"
          >
            <path d={ICON_PATH} />
          </svg>
        </span>
        <span className="sr-only">{title}</span>
      </span>
    </Tag>
  );
}
