import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { btnSm } from "../../lib/uiClasses";

/**
 * Markdown preview for an artifact's body — summaries, and codebook/coding
 * comparisons.
 *
 * Three things this has to do that a bare `<ReactMarkdown>` does not:
 *
 * 1. `remark-gfm`. The compare prompt literally asks the model to "return
 *    the full comparison in a markdown format" and the summarize prompt asks
 *    for code frequencies and distributions, so pipe tables are the single
 *    most common structure in this content — and they are not CommonMark.
 * 2. Element styling. Tailwind's preflight strips heading sizes, list
 *    markers and table borders, and this project deliberately has no
 *    `@tailwindcss/typography` plugin, so every tag is styled here from the
 *    app's own tokens.
 * 3. Read as a document, not as UI. This used to size body copy at
 *    `text-sm` with `text-xl` h1s — dense-UI sizing for text a researcher
 *    actually reads end to end. The scale below is a document scale.
 *
 * Prose keeps a ~75ch measure per block; tables are deliberately exempt and
 * scroll inside their own box, because a six-column comparison squeezed into
 * a reading measure was the original complaint. Code blocks and tables carry
 * a copy button — lifting a comparison table into a paper or a spreadsheet
 * is the actual workflow these pages exist for.
 *
 * No syntax highlighter: colour in this app is reserved for error, success
 * and per-code identity (documentation/style-guide.md), and this content is
 * research prose, not code.
 */
const PROSE = "max-w-[75ch]";

/** react-markdown hands every component the mdast `node`, which must not
 * reach the DOM element. */
function domProps(props) {
  const rest = { ...props };
  delete rest.node;
  return rest;
}

/** Flatten a React children tree to its text, for the clipboard. */
function toText(children) {
  if (children == null || typeof children === "boolean") return "";
  if (typeof children === "string" || typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(toText).join("");
  return toText(children.props?.children);
}

function CopyButton({ getText, label = "Copy" }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(getText());
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be denied outright; a dead button is a better
      // outcome than a thrown error over the whole preview.
      setCopied(false);
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      // Hidden until the block is hovered or the button is focused, so a
      // long document isn't peppered with controls.
      className={`${btnSm} absolute right-1 top-1 z-10 bg-ink opacity-0 transition-opacity focus:opacity-100 group-hover:opacity-100`}
    >
      {copied ? "Copied" : label}
    </button>
  );
}

/** Fenced code block: bordered, monospace, with its language named and a
 * copy button. Overrides the global `pre { white-space: pre-wrap }` from
 * index.css so long lines scroll instead of wrapping — wrapping is right for
 * an LLM answer accidentally fenced whole, wrong for actual code. */
function CodeBlock(props) {
  const child = Array.isArray(props.children) ? props.children[0] : props.children;
  const className = child?.props?.className || "";
  const language = /language-([\w-]+)/.exec(className)?.[1] || "";
  const text = toText(child?.props?.children).replace(/\n$/, "");

  return (
    <div className="group relative my-4 border border-line bg-surface-raised">
      {language ? (
        <div className="border-b border-line-soft px-3 py-1 text-[11px] uppercase tracking-wide text-paper/50">
          {language}
        </div>
      ) : null}
      <CopyButton getText={() => text} />
      <pre className="overflow-x-auto p-3 text-[13px] [white-space:pre]">
        <code>{text}</code>
      </pre>
    </div>
  );
}

/** Copies the table as TSV, which is what a spreadsheet expects on paste.
 * Read off the rendered DOM rather than the mdast, so what you copy is the
 * table you can see -- but via `textContent`, not `innerText`, so the header
 * row's cosmetic `uppercase` doesn't get baked into the clipboard. */
function tableToTsv(table) {
  if (!table) return "";
  return [...table.rows]
    .map((row) => [...row.cells].map((cell) => cell.textContent.trim().replace(/\s+/g, " ")).join("\t"))
    .join("\n");
}

function MarkdownTable(props) {
  const ref = useRef(null);
  return (
    <div className="group relative my-4">
      <CopyButton getText={() => tableToTsv(ref.current)} label="Copy TSV" />
      {/* The scroll box is a sibling of the button, not its parent, so the
          button stays put while the table scrolls under it. */}
      <div className="max-w-full overflow-x-auto border border-line">
        <table ref={ref} className="w-full border-collapse text-sm" {...domProps(props)} />
      </div>
    </div>
  );
}

const components = {
  h1: (props) => (
    <h1 className={`mt-8 mb-3 text-2xl font-bold first:mt-0 ${PROSE}`} {...domProps(props)} />
  ),
  h2: (props) => (
    <h2
      className={`mt-8 mb-3 border-b border-line pb-1.5 text-xl font-bold first:mt-0 ${PROSE}`}
      {...domProps(props)}
    />
  ),
  h3: (props) => (
    <h3 className={`mt-6 mb-2 text-lg font-semibold first:mt-0 ${PROSE}`} {...domProps(props)} />
  ),
  h4: (props) => (
    <h4 className={`mt-5 mb-2 text-base font-semibold first:mt-0 ${PROSE}`} {...domProps(props)} />
  ),
  h5: (props) => (
    <h5
      className={`mt-4 mb-1.5 text-sm font-semibold uppercase tracking-wide first:mt-0 ${PROSE}`}
      {...domProps(props)}
    />
  ),
  h6: (props) => (
    <h6
      className={`mt-4 mb-1.5 text-xs font-semibold uppercase tracking-wide text-paper/70 first:mt-0 ${PROSE}`}
      {...domProps(props)}
    />
  ),
  p: (props) => (
    <p className={`my-4 text-base leading-relaxed first:mt-0 ${PROSE}`} {...domProps(props)} />
  ),
  ul: (props) => (
    <ul
      className={`my-4 list-disc space-y-1 pl-6 text-base leading-relaxed marker:text-paper/50 ${PROSE}`}
      {...domProps(props)}
    />
  ),
  ol: (props) => (
    <ol
      className={`my-4 list-decimal space-y-1 pl-6 text-base leading-relaxed marker:text-paper/50 ${PROSE}`}
      {...domProps(props)}
    />
  ),
  // Nested lists sit tighter than top-level ones and must not re-apply the
  // block margin, or each level compounds the spacing.
  li: (props) => <li className="[&>ul]:my-1 [&>ol]:my-1" {...domProps(props)} />,
  // Evidence quoting is first-class here: the summarize prompt asks for
  // "representative quotes or examples".
  blockquote: (props) => (
    <blockquote
      className={`my-4 border-l-2 border-line-strong bg-surface py-1 pl-4 text-base italic leading-relaxed text-paper/80 ${PROSE}`}
      {...domProps(props)}
    />
  ),
  hr: (props) => <hr className="my-8 border-t border-line" {...domProps(props)} />,
  a: (props) => (
    <a className="underline decoration-dotted underline-offset-2" target="_blank" rel="noreferrer" {...domProps(props)} />
  ),
  strong: (props) => <strong className="font-semibold" {...domProps(props)} />,
  em: (props) => <em className="italic" {...domProps(props)} />,
  del: (props) => <del className="line-through text-paper/50" {...domProps(props)} />,
  img: (props) => <img className="my-4 max-w-full border border-line" {...domProps(props)} />,
  // GFM task lists. `disabled` comes from remark-gfm; keep them read-only,
  // this is a rendered artifact, not a form.
  input: (props) =>
    props.type === "checkbox" ? (
      <input
        className="mr-2 h-3.5 w-3.5 translate-y-[1px] accent-paper"
        {...domProps(props)}
        readOnly
      />
    ) : (
      <input {...domProps(props)} />
    ),
  code: ({ className, ...props }) =>
    // A fenced block arrives wrapped in <pre>, handled by CodeBlock; only
    // the inline form needs its own box.
    className?.includes("language-") ? (
      <code className={className} {...domProps(props)} />
    ) : (
      <code
        className="border border-line-soft bg-surface-raised px-1 py-0.5 font-mono text-[0.85em]"
        {...domProps(props)}
      />
    ),
  pre: CodeBlock,
  table: MarkdownTable,
  thead: (props) => <thead className="bg-surface-raised" {...domProps(props)} />,
  th: (props) => (
    <th
      className="border-b border-line border-r border-line-soft px-3 py-2 text-left align-top text-xs font-semibold uppercase tracking-wide text-paper/70 last:border-r-0"
      {...domProps(props)}
    />
  ),
  td: (props) => (
    <td
      className="border-b border-r border-line-soft px-3 py-2 align-top leading-relaxed tabular-nums last:border-r-0"
      {...domProps(props)}
    />
  ),
  tr: (props) => <tr className="last:[&>td]:border-b-0" {...domProps(props)} />,
  // Footnote block at the foot of the document.
  section: (props) =>
    props["data-footnotes"] !== undefined ? (
      <section
        className={`mt-8 border-t border-line pt-3 text-sm text-paper/70 ${PROSE}`}
        {...domProps(props)}
      />
    ) : (
      <section {...domProps(props)} />
    ),
  sup: (props) => <sup className="text-[0.7em]" {...domProps(props)} />,
};

export default function MarkdownDisplay({ content, className }) {
  if (!content) return null;

  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
