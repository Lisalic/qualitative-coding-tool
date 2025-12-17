import "../styles/DataTable.css";

export default function EntryModal({ entry, isOpen, onClose }) {
  if (!isOpen || !entry) return null;

  const formatDate = (timestamp) => {
    if (!timestamp) return "N/A";
    return new Date(timestamp * 1000).toLocaleString();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            {entry.type === "submission" ? "Submission" : "Comment"} Details
          </h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          {entry.type === "submission" ? (
            <>
              <div className="detail-row">
                <strong>ID:</strong> {entry.id}
              </div>
              {entry.subreddit && (
                <div className="detail-row">
                  <strong>Subreddit:</strong> {entry.subreddit}
                </div>
              )}
              <div className="detail-row">
                <strong>Title:</strong> {entry.title}
              </div>
              {entry.selftext && (
                <div className="detail-row">
                  <strong>Selftext:</strong>
                  <div className="detail-text">{entry.selftext}</div>
                </div>
              )}
              {entry.author && (
                <div className="detail-row">
                  <strong>Author:</strong> {entry.author}
                </div>
              )}
              {entry.score !== undefined && (
                <div className="detail-row">
                  <strong>Score:</strong> {entry.score}
                </div>
              )}
              {entry.created_utc && (
                <div className="detail-row">
                  <strong>Created:</strong> {formatDate(entry.created_utc)}
                </div>
              )}
              {entry.num_comments !== undefined && (
                <div className="detail-row">
                  <strong>Number of Comments:</strong> {entry.num_comments}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="detail-row">
                <strong>ID:</strong> {entry.id}
              </div>
              <div className="detail-row">
                <strong>Subreddit:</strong> {entry.subreddit}
              </div>
              <div className="detail-row">
                <strong>Body:</strong>
                <div className="detail-text">{entry.body}</div>
              </div>
              <div className="detail-row">
                <strong>Author:</strong> {entry.author}
              </div>
              <div className="detail-row">
                <strong>Score:</strong> {entry.score}
              </div>
              {entry.created_utc && (
                <div className="detail-row">
                  <strong>Created:</strong> {formatDate(entry.created_utc)}
                </div>
              )}
              {entry.link_id && (
                <div className="detail-row">
                  <strong>Link ID:</strong> {entry.link_id}
                </div>
              )}
              {entry.parent_id && (
                <div className="detail-row">
                  <strong>Parent ID:</strong> {entry.parent_id}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
