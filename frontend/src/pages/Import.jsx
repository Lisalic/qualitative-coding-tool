import FileUpload from "../components/data/FileUpload";
import PageShell from "../components/shell/PageShell";

export default function ImportPage() {
  const handleUploadSuccess = () => {};

  return (
    <PageShell title="Import Data" width="wide">
      <FileUpload onUploadSuccess={handleUploadSuccess} />
    </PageShell>
  );
}
