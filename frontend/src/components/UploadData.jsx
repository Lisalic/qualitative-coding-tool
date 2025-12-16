import FileUpload from "./FileUpload";

export default function UploadData({ onUploadSuccess, onError }) {
  return (
    <div className="upload-section">
      <FileUpload onUploadSuccess={onUploadSuccess} onError={onError} />
    </div>
  );
}
