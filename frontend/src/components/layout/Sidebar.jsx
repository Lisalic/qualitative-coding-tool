import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

const navBtn =
  "w-full px-3 py-2 text-left text-sm transition-colors hover:bg-white/10";

export default function Sidebar() {
  const { status } = useAuth();
  const isAuth = status === "auth";
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const stored = localStorage.getItem("sidebarCollapsed");
      if (stored !== null) return stored === "true";
      // No explicit preference yet: default collapsed on narrow viewports
      // so the sidebar doesn't eat most of the screen on first load.
      return typeof window !== "undefined" && window.innerWidth < 768;
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

  const collapse = () => {
    setCollapsed(true);
    try {
      localStorage.setItem("sidebarCollapsed", "true");
      window.dispatchEvent(new Event("sidebar-toggle"));
    } catch (e) {}
  };

  return (
    <aside className="flex w-[190px] shrink-0 flex-col border-r border-paper">
      <div className="flex justify-end p-1.5">
        <button
          type="button"
          className="px-2 py-1 text-sm transition-colors hover:bg-white/10"
          aria-label="Collapse sidebar"
          onClick={collapse}
        >
          ✕
        </button>
      </div>

      {!isAuth ? (
        <nav className="flex flex-col pb-2">
          {items.map(([label, path]) => (
            <button
              key={path}
              type="button"
              className={navBtn}
              onClick={() => navigate(path)}
            >
              {label}
            </button>
          ))}
        </nav>
      ) : (
        (() => {
          const pipelineOrder = [
            "Home",
            "Import Data",
            "Filter Data",
            "Generate Codebook",
            "Apply Codebook",
            "Compare Codebook",
            "Compare Coding",
            "Summarize Coding",
          ];
          const viewOrder = [
            "View Data",
            "View Filtered Data",
            "View Codebook",
            "View Coding",
            "View Summary",
          ];

          const mapByLabel = Object.fromEntries(
            items.map(([label, path]) => [label, path]),
          );

          const renderGroup = (labels) =>
            labels
              .filter((label) => label in mapByLabel)
              .map((label) => (
                <button
                  key={mapByLabel[label]}
                  type="button"
                  className={navBtn}
                  onClick={() => navigate(mapByLabel[label])}
                >
                  {label}
                </button>
              ));

          return (
            <nav className="flex flex-col pb-2">
              {renderGroup(pipelineOrder)}
              <div className="mt-2 border-t border-paper/20 px-3 pb-1 pt-2 text-xs uppercase tracking-wide text-paper/50">
                Views
              </div>
              {renderGroup(viewOrder)}
            </nav>
          );
        })()
      )}
    </aside>
  );
}
