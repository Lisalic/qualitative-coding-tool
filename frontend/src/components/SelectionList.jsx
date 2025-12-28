import React from "react";

export default function SelectionList({
  items = [],
  selectedId,
  onSelect = () => {},
  className = "selector-list",
  buttonClass = "db-button",
  emptyMessage = "No items available",
}) {
  if (!items || items.length === 0) {
    return (
      <div className={className}>
        <p style={{ color: "#ffffff" }}>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={className}>
      {items.map((it) => (
        <button
          key={it.id}
          className={`${buttonClass} ${selectedId === it.id ? "active" : ""}`}
          onClick={() => onSelect(it.id)}
        >
          {it.name ?? it.id}
        </button>
      ))}
    </div>
  );
}
