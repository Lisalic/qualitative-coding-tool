import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

const navBtn =
  "w-full px-3 py-1.5 text-left text-sm transition-colors hover:bg-white/10";
const navBtnActive = "bg-paper text-ink hover:bg-paper";

const AUTH_ITEMS = [
  ["Home", "/"],
  ["Import Data", "/import"],
  ["Filter Data", "/filter"],
  ["Filter Editor", "/filter-editor"],
  ["Generate Codebook", "/codebook-generate"],
  ["Apply Codebook", "/codebook-apply"],
  ["Compare Codebook", "/compare-codebook"],
  ["Compare Coding", "/compare-coding"],
  ["Summarize Coding", "/summarize-coding"],
];

const VIEW_ITEMS = [
  ["View Data", "/data"],
  ["View Filtered Data", "/filtered-data"],
  ["View Codebook", "/codebook-view"],
  ["View Coding", "/coding-view"],
  ["View Summary", "/summaryview"],
  ["View Codebook Comparisons", "/codebook-comparison-view"],
  ["View Coding Comparisons", "/coding-comparison-view"],
  ["View Lineage", "/lineage"],
  ["Version History", "/versions"],
];

const ANON_ITEMS = [
  ["Login", "/login"],
  ["Register", "/register"],
];

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
      // Private browsing / blocked storage: fall back to expanded.
      return false;
    }
  });
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const handler = () => {
      try {
        setCollapsed(localStorage.getItem("sidebarCollapsed") === "true");
      } catch (e) {
        // Storage unavailable: keep whatever state we already have.
      }
    };
    window.addEventListener("sidebar-toggle", handler);
    return () => window.removeEventListener("sidebar-toggle", handler);
  }, []);

  if (status === "loading") return null;

  const collapse = () => {
    setCollapsed(true);
    try {
      localStorage.setItem("sidebarCollapsed", "true");
      window.dispatchEvent(new Event("sidebar-toggle"));
    } catch (e) {
      // Storage unavailable: the collapse still applies for this session.
    }
  };

  const pipeline = isAuth ? AUTH_ITEMS : ANON_ITEMS;
  const views = isAuth ? VIEW_ITEMS : [];

  // "/" would prefix-match every route, so it only ever matches exactly.
  const isActive = (path) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  if (collapsed) return null;

  const renderGroup = (entries) =>
    entries.map(([label, path]) => (
      <button
        key={path}
        type="button"
        aria-current={isActive(path) ? "page" : undefined}
        className={`${navBtn} ${isActive(path) ? navBtnActive : ""}`}
        onClick={() => navigate(path)}
      >
        {label}
      </button>
    ));

  return (
    <aside className="flex w-[190px] shrink-0 flex-col overflow-y-auto border-r border-paper">
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

      <nav className="flex flex-col pb-2">
        {renderGroup(pipeline)}
        {views.length > 0 ? (
          <>
            <div className="mt-2 border-t border-line px-3 pb-1 pt-2 text-xs uppercase tracking-wide text-paper/50">
              Views
            </div>
            {renderGroup(views)}
          </>
        ) : null}
      </nav>
    </aside>
  );
}
