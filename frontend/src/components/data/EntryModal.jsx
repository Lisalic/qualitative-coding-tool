import { useState, useEffect } from "react";
import { apiFetch } from "../../api";
import MemoEditor from "./MemoEditor";

const navBtn =
  "border border-paper px-3 py-1.5 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

/**
 * `memo`/`onSaveMemo` are optional: every caller that renders rows from a
 * real database passes them, and the modal simply omits the memo section
 * when they are absent. Because the raw viewer, the filtered viewer and
 * the filter editor all open this same modal, wiring the memo editor here
 * once is what makes "add a memo to any row" true everywhere rather than
 * on one screen.
 */
export default function EntryModal({
  entry,
  isOpen,
  onClose,
  database = "",
  onPrev,
  onNext,
  hasPrev = false,
  hasNext = false,
  memo = null,
  onSaveMemo = null,
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
      const response = await apiFetch(
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
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-[85%] max-w-[1100px] overflow-y-auto border-2 border-paper bg-ink"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-2 border-b border-paper px-6 py-4">
          <div className="flex items-center gap-2">
            <button type="button" onClick={onPrev} className={navBtn} disabled={!hasPrev}>
              Previous
            </button>
            <button type="button" onClick={onNext} className={navBtn} disabled={!hasNext}>
              Next
            </button>
          </div>
          <h2 className="text-xl font-semibold">
            {entry.type === "submission" ? "Post" : "Comment"} Details
          </h2>
          <button
            type="button"
            className="flex h-9 w-9 items-center justify-center text-xl transition-colors hover:bg-white/10"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="p-6">
          {entry.type === "submission" ? (
            <>
              <div className="mb-3">
                <strong>ID:</strong> {entry.id}
              </div>
              {entry.subreddit && (
                <div className="mb-3">
                  <strong>Subreddit:</strong> {entry.subreddit}
                </div>
              )}
              <div className="mb-3">
                <strong>Title:</strong> {entry.title}
              </div>
              {entry.selftext && (
                <div className="mb-3">
                  <strong>Selftext:</strong>
                  <div className="mt-1 whitespace-pre-wrap text-paper/80">
                    {entry.selftext}
                  </div>
                </div>
              )}
              {entry.author && (
                <div className="mb-3">
                  <strong>Author:</strong> {entry.author}
                </div>
              )}
              {entry.score !== undefined && (
                <div className="mb-3">
                  <strong>Score:</strong> {entry.score}
                </div>
              )}
              {entry.created_utc && (
                <div className="mb-3">
                  <strong>Created:</strong> {formatDate(entry.created_utc)}
                </div>
              )}
              {entry.num_comments !== undefined && (
                <div className="mb-3">
                  <strong>Number of Comments:</strong> {entry.num_comments}
                </div>
              )}
              {entry.type === "submission" && (
                <div className="mt-6 border-t border-paper/20 pt-4">
                  <h3 className="mb-3 text-lg font-medium">
                    Comments ({comments.length})
                  </h3>
                  {loadingComments ? (
                    <p className="text-paper/70">Loading comments...</p>
                  ) : comments.length > 0 ? (
                    <div className="flex flex-col gap-3">
                      {comments.map((comment) => (
                        <div key={comment.id} className="border border-paper/20 p-3">
                          <div className="text-sm text-paper/70">
                            <strong>{comment.author}</strong> •{" "}
                            {formatDate(comment.created_utc)}
                          </div>
                          <div className="mt-1 whitespace-pre-wrap">{comment.body}</div>
                          <div className="mt-1 text-xs text-paper/50">
                            Score: {comment.score}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-paper/70">No comments found in this database.</p>
                  )}
                </div>
              )}
            </>
          ) : (
            <>
              <div className="mb-3">
                <strong>ID:</strong> {entry.id}
              </div>
              <div className="mb-3">
                <strong>Subreddit:</strong> {entry.subreddit}
              </div>
              <div className="mb-3">
                <strong>Body:</strong>
                <div className="mt-1 whitespace-pre-wrap text-paper/80">{entry.body}</div>
              </div>
              <div className="mb-3">
                <strong>Author:</strong> {entry.author}
              </div>
              <div className="mb-3">
                <strong>Score:</strong> {entry.score}
              </div>
              {entry.created_utc && (
                <div className="mb-3">
                  <strong>Created:</strong> {formatDate(entry.created_utc)}
                </div>
              )}
              {entry.link_id && (
                <div className="mb-3">
                  <strong>Link ID:</strong> {entry.link_id}
                </div>
              )}
              {entry.parent_id && (
                <div className="mb-3">
                  <strong>Parent ID:</strong> {entry.parent_id}
                </div>
              )}
            </>
          )}
          {onSaveMemo && (
            <MemoEditor
              key={`${entry.type}:${entry.id}`}
              memo={memo}
              onSave={(body) => onSaveMemo(entry.type, entry.id, body)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
