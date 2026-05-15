import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import "../../styles/Home.css";

export default function Sidebar() {
  const { status } = useAuth();
  const isAuth = status === "auth";
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("sidebarCollapsed") === "true";
    } catch (e) {
      return false;
    }
  });
  const navigate = useNavigate();

  useEffect(() => {
    const handler = () => {
      try {
        setCollapsed(localStorage.getItem("sidebarCollapsed") === "true");
      } catch (e) {}
    };
    window.addEventListener("sidebar-toggle", handler);
    return () => window.removeEventListener("sidebar-toggle", handler);
  }, []);

  if (status === "loading") return null;

  const authButtons = [
    ["Home", "/"],
    ["Import Data", "/import"],
    ["View Data", "/data"],
    ["Filter Data", "/filter"],
    ["View Filtered Data", "/filtered-data"],
    ["Generate Codebook", "/codebook-generate"],
    ["View Codebook", "/codebook-view"],
    ["Apply Codebook", "/codebook-apply"],
    ["Compare Codebook", "/compare-codebook"],
    ["Compare Coding", "/compare-coding"],
    ["Summarize Coding", "/summarize-coding"],
    ["View Summary", "/summaryview"],
    ["View Coding", "/coding-view"],
  ];

  const anonButtons = [
    ["Login", "/login"],
    ["Register", "/register"],
  ];

  const items = isAuth ? authButtons : anonButtons;

  if (collapsed) return null;

  return (
    <aside className="app-shell__sidebar">
      <div className="sidebar__header">
        <button
          className="sidebar__close"
          aria-label="Collapse sidebar"
          onClick={() => {
            setCollapsed(true);
            try {
              localStorage.setItem("sidebarCollapsed", "true");
              // notify navbar and other listeners
              window.dispatchEvent(new Event("sidebar-toggle"));
            } catch (e) {}
          }}
        >
          ✕
        </button>
      </div>

      {(() => {
        if (!isAuth) {
          return items.map(([label, path]) => (
            <button
              key={path}
              className="sidebar__button"
              onClick={() => navigate(path)}
            >
              {label}
            </button>
          ));
        }

        const order = [
          "Home",
          "Import Data",
          "Filter Data",
          "Generate Codebook",
          "Apply Codebook",
          "Compare Codebook",
          "Compare Coding",
          "Summarize Coding",
          "View Data",
          "View Filtered Data",
          "View Codebook",
          "View Coding",
          "View Summary",
        ];

        const mapByLabel = Object.fromEntries(
          items.map(([label, path]) => [label, path]),
        );

        return order
          .filter((label) => label in mapByLabel)
          .map((label) => (
            <button
              key={mapByLabel[label]}
              className="sidebar__button"
              onClick={() => navigate(mapByLabel[label])}
            >
              {label}
            </button>
          ));
      })()}
    </aside>
  );
}
