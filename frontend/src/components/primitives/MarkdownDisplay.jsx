import ReactMarkdown from "react-markdown";

export default function MarkdownDisplay({
  content,
  title,
  className,
  style,
  innerClassName,
  innerStyle,
  titleStyle,
}) {
  if (!content) return null;

  const markdown = <ReactMarkdown>{content}</ReactMarkdown>;

  return (
    <div className={className} style={style}>
      {title ? <h3 style={titleStyle}>{title}</h3> : null}
      {innerClassName || innerStyle ? (
        <div className={innerClassName} style={innerStyle}>
          {markdown}
        </div>
      ) : (
        markdown
      )}
    </div>
  );
}
