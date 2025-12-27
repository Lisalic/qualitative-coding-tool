import FileUpload from "./FileUpload";

export default function UploadData({ onUploadSuccess, onView }) {
  return (
    <div className="left-section">
      <FileUpload onUploadSuccess={onUploadSuccess} onView={onView} />
    </div>
  );
}
