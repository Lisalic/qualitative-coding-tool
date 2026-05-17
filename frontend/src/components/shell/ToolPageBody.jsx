export default function ToolPageBody({
  children,
  className = "single-panel-layout",
}) {
  return <div className={className}>{children}</div>;
}
