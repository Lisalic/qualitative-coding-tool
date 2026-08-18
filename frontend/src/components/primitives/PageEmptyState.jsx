const DEFAULT_CLASSES =
  "border border-paper/20 bg-white/[0.02] px-4 py-6 text-center italic text-paper/70";

export default function PageEmptyState({ message, className = DEFAULT_CLASSES, style }) {
  return (
    <div className={className} style={style}>
      {message}
    </div>
  );
}
