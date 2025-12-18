import { useState, useEffect } from "react";
import "../styles/DataTable.css";

export default function EntryModal({
  entry,
  isOpen,
  onClose,
  database = "original",
}) {
  const [comments, setComments] = useState([]);
  const [loadingComments, setLoadingComments] = useState(false);

  useEffect(() => {
    if (isOpen && entry && entry.type === "submission") {
      fetchComments(entry.id);
    } else {
      setComments([]);
    }
  }, [isOpen, entry]);

  const fetchComments = async (submissionId) => {
    try {
      setLoadingComments(true);
      const response = await fetch(
        `/api/comments/${submissionId}?database=${database}`
      );
      if (!response.ok) throw new Error("Failed to fetch comments");
      const data = await response.json();
      setComments(data.comments || []);
    } catch (err) {
      console.error("Error fetching comments:", err);
      setComments([]);
    } finally {
      setLoadingComments(false);
    }
  };

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
              {entry.type === "submission" && (
                <div className="comments-section">
                  <h3>Comments ({comments.length})</h3>
                  {loadingComments ? (
                    <p>Loading comments...</p>
                  ) : comments.length > 0 ? (
                    <div className="comments-list">
                      {comments.map((comment) => (
                        <div key={comment.id} className="comment-item">
                          <div className="comment-header">
                            <strong>{comment.author}</strong> •{" "}
                            {formatDate(comment.created_utc)}
                          </div>
                          <div className="comment-body">{comment.body}</div>
                          <div className="comment-meta">
                            Score: {comment.score}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p>No comments found in this database.</p>
                  )}
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
