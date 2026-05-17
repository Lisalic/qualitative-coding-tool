export default function PageEmptyState({ message, className = "empty-state", style }) {
  return (
    <div className={className} style={style}>
      {message}
    </div>
  );
}
