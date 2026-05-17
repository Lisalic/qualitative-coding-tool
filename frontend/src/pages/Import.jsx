import { useNavigate } from "react-router-dom";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import FileUpload from "../components/data/FileUpload";
import ToolPage from "../components/shell/ToolPage";
import "../styles/Home.css";
import "../styles/Data.css";

const HIDDEN_ERROR_MATCHES = [
  "select at least",
  "enter a name",
  "Database",
  "merge",
];

function isCriticalError(error) {
  if (!error) return false;
  return !HIDDEN_ERROR_MATCHES.some((text) => error.includes(text));
}

export default function ImportPage() {
  const navigate = useNavigate();

  const handleUploadSuccess = () => {};

  const handleViewData = () => {
    navigate("/data");
  };

  const handleDismissError = () => {};
  const error = "";
  const displayError = isCriticalError(error) ? error : null;

  return (
    <ToolPage
      beforeBody={<ErrorDisplay message={displayError} onDismiss={handleDismissError} />}
    >
      <div className="left-section">
        <FileUpload onUploadSuccess={handleUploadSuccess} onView={handleViewData} />
      </div>
    </ToolPage>
  );
}
