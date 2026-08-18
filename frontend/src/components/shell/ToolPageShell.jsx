export default function ToolPageShell({
  children,
  className = "mx-auto w-full max-w-4xl px-4 py-10",
}) {
  return <div className={className}>{children}</div>;
}
