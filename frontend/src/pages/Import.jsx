import FileUpload from "../features/data/FileUpload";
import PageShell from "../components/layout/PageShell";

export default function ImportPage() {
  const handleUploadSuccess = () => {};

  return (
    <PageShell title="Import Data" width="wide">
      <FileUpload onUploadSuccess={handleUploadSuccess} />
    </PageShell>
  );
}
