import { useNavigate } from "react-router-dom";
import FileUpload from "../components/data/FileUpload";
import ToolPage from "../components/shell/ToolPage";

export default function ImportPage() {
  const navigate = useNavigate();

  const handleUploadSuccess = () => {};

  const handleViewData = () => {
    navigate("/data");
  };

  return (
    <ToolPage>
      <FileUpload onUploadSuccess={handleUploadSuccess} onView={handleViewData} />
    </ToolPage>
  );
}
