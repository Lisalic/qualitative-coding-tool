import React from "react";

export default function SelectionList({
  items = [],
  selectedId,
  onSelect = () => {},
  className = "mb-6 flex flex-wrap gap-2.5 border-2 border-paper p-4",
  buttonClass = "border border-paper px-4 py-2.5 text-sm transition-colors hover:bg-paper hover:text-ink",
  selectedButtonClass = "bg-paper text-ink",
  emptyMessage = "No items available",
}) {
  if (!items || items.length === 0) {
    return (
      <div className={className}>
        <p className="text-paper">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={className}>
      {items.map((it) => {
        const isSelected = selectedId === it.id;
        return (
          <button
            key={it.id}
            type="button"
            className={`${buttonClass} ${isSelected ? `active ${selectedButtonClass}` : ""}`}
            onClick={() => onSelect(it.id)}
          >
            {it.display_name ?? it.name ?? it.id}
          </button>
        );
      })}
    </div>
  );
}
