import ToolPageBody from "./ToolPageBody";
import ToolPageShell from "./ToolPageShell";
import ToolPanelHost from "./ToolPanelHost";

export default function ToolPage({
  children,
  shellClassName,
  bodyProps,
  beforeBody = null,
}) {
  return (
    <ToolPageShell className={shellClassName}>
      {beforeBody}
      <ToolPageBody {...bodyProps}>
        <ToolPanelHost>{children}</ToolPanelHost>
      </ToolPageBody>
    </ToolPageShell>
  );
}
