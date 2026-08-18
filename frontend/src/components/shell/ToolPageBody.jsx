export default function ToolPageBody({
  children,
  className = "flex w-full justify-center",
}) {
  return <div className={className}>{children}</div>;
}
