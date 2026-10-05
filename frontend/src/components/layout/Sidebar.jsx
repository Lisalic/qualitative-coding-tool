import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { confirmLeave } from "../feedback/LeaveGuard";

const navBtn = "block w-full px-3 py-1.5 text-left text-sm transition-colors";
// Text color is set per state rather than in `navBtn`: these are links,
// and two competing text utilities on one element resolve by stylesheet
// order, not class order -- the active item's text vanished white-on-white.
const navBtnInactive = "text-paper hover:bg-white/10 hover:text-paper";
const navBtnActive = "bg-paper text-ink hover:bg-paper hover:text-ink";

const AUTH_ITEMS = [
  ["Projects", "/"],
  ["Import Data", "/import"],
  ["Filter Data", "/filter"],
  ["Create Codebook", "/codebook"],
  ["Compare Codebook", "/compare-codebook"],
  ["Integrate Codebook", "/integrate-codebook"],
  ["Apply Codebook", "/codebook-apply"],
  ["Compare Coding", "/compare-coding"],
  ["Summarize Coding", "/summarize-coding"],
];

const VIEW_ITEMS = [
  ["View Data", "/data"],
  ["View Filtered Data", "/filtered-data"],
  ["View Codebook", "/codebook-view"],
  ["View Codebook Comparison", "/codebook-comparison-view"],
  ["View Coding", "/coding-view"],
  ["View Coding Comparison", "/coding-comparison-view"],
  ["View Summary", "/summaryview"],
  ["View Lineage", "/lineage"],
  ["Version History", "/versions"],
];

const ANON_ITEMS = [
  ["Log in", "/login"],
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

  // Exact path, or a real sub-path of it. A bare `startsWith` lit up
  // every item whose route is a string prefix of another's -- "/codebook"
  // matched "/codebook-apply", "/filter" matched "/filtered-data" -- so
  // two entries read as the current page at once.
  const isActive = (path) =>
    location.pathname === path ||
    location.pathname.startsWith(`${path}/`) ||
    // A project's own page sits under the project list.
    (path === "/" && location.pathname.startsWith("/project/"));

  // Real links (middle-click / open in new tab work), but a plain click
  // still checks for unsaved editor work first, and on a narrow screen
  // closes the sidebar so the page it opened is visible.
  const handleNavClick = async (event, path) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    event.preventDefault();
    if (!(await confirmLeave())) return;
    navigate(path);
    if (typeof window !== "undefined" && window.innerWidth < 768) collapse();
  };

  if (collapsed) return null;

  const renderGroup = (entries) =>
    entries.map(([label, path]) => (
      <Link
        key={path}
        to={path}
        aria-current={isActive(path) ? "page" : undefined}
        className={`${navBtn} ${isActive(path) ? navBtnActive : navBtnInactive}`}
        onClick={(event) => handleNavClick(event, path)}
      >
        {label}
      </Link>
    ));

  return (
    <aside className="flex w-[190px] shrink-0 flex-col overflow-y-auto border-r border-paper">
      <div className="flex justify-end p-1.5">
        <button
          type="button"
          className="px-2.5 py-1.5 text-sm transition-colors hover:bg-white/10"
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
