import { useNavigate } from "react-router-dom";
import ErrorDisplay from "../components/ErrorDisplay";
import UploadData from "../components/UploadData";
import { useState } from "react";
import "../styles/Home.css";
import "../styles/Data.css";

export default function Import() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [uploadData, setUploadData] = useState(null);

  const handleUploadSuccess = (data) => {
    setUploadData(data);
  };

  const handleViewData = () => {
    navigate("/data");
  };

  const handleDismissError = () => {
    setError("");
  };

  return (
    <>
      <div className="home-container">
        {error &&
          !error.includes("select at least") &&
          !error.includes("enter a name") &&
          !error.includes("Database") &&
          !error.includes("merge") && (
            <ErrorDisplay message={error} onDismiss={handleDismissError} />
          )}

        <div className="tool-page-layout">
          <UploadData
            onUploadSuccess={handleUploadSuccess}
            onView={handleViewData}
          />
        </div>
      </div>
    </>
  );
}
