import { useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { apiFetch, api } from "../api";
import "./Navbar.css";

function Navbar({ showBack, onBack }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [apiKey, setApiKey] = useState("");
  const [showApiInput, setShowApiInput] = useState(false);
  const [isAuth, setIsAuth] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem("sidebarCollapsed") === "true";
    } catch (e) {
      return false;
    }
  });

  useEffect(() => {
    const savedKey = localStorage.getItem("apiKey");
    if (savedKey) {
      setApiKey(savedKey);
    }
    const checkAuth = () => {
      apiFetch("/api/me/")
        .then((r) => setIsAuth(!!r.ok))
        .catch(() => setIsAuth(false));
    };

    checkAuth();

    const handler = () => checkAuth();
    window.addEventListener("auth-changed", handler);
    return () => window.removeEventListener("auth-changed", handler);
  }, []);

  useEffect(() => {
    const handler = () => {
      try {
        setSidebarCollapsed(
          localStorage.getItem("sidebarCollapsed") === "true"
        );
      } catch (e) {
        setSidebarCollapsed(false);
      }
    };
    window.addEventListener("sidebar-toggle", handler);
    return () => window.removeEventListener("sidebar-toggle", handler);
  }, []);

  const handleSaveApiKey = () => {
    localStorage.setItem("apiKey", apiKey);
    setShowApiInput(false);
    alert("API Key saved!");
  };

  const shouldShowBack =
    showBack !== undefined ? showBack : location.pathname !== "/";

  const handleBack = onBack || (() => navigate("/"));

  return (
    <nav className="nav-bar">
      <div className="nav-bar__inner">
        <button
          className="nav-toggle"
          aria-label="Toggle sidebar"
          onClick={() => {
            try {
              const cur = localStorage.getItem("sidebarCollapsed") === "true";
              localStorage.setItem("sidebarCollapsed", (!cur).toString());
            } catch (e) {}
            window.dispatchEvent(new Event("sidebar-toggle"));
            setSidebarCollapsed((s) => !s);
          }}
        >
          ☰
        </button>
        {shouldShowBack && (
          <button className="nav-back" onClick={handleBack}>
            ← Back
          </button>
        )}
        <div
          className="nav-brand"
          onClick={() => navigate("/")}
          style={{ cursor: "pointer" }}
        >
          Qualitative Coding Tool
        </div>
        <div className="nav-actions">
          {showApiInput ? (
            <div className="api-input-group">
              <input
                type="password"
                placeholder="Enter API Key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="nav-input"
              />
              <button onClick={handleSaveApiKey} className="nav-button">
                Save
              </button>
              <button
                onClick={() => setShowApiInput(false)}
                className="nav-button nav-button--muted"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowApiInput(true)}
              className="nav-button"
            >
              {apiKey ? "API Key Set" : "Set API Key"}
            </button>
          )}
          {isAuth ? (
            <button
              className="nav-logout"
              onClick={async () => {
                try {
                  await apiFetch("/api/logout/", { method: "POST" });
                } catch (e) {
                  // ignore
                }
                // clear local token and axios header
                try {
                  localStorage.removeItem("access_token");
                  delete api.defaults.headers.common["Authorization"];
                } catch (e) {}
                setIsAuth(false);
                // notify other components that auth changed
                window.dispatchEvent(new Event("auth-changed"));
                navigate("/");
              }}
            >
              Logout
            </button>
          ) : (
            <button
              className="nav-button"
              onClick={() => {
                navigate("/login");
              }}
            >
              Log in
            </button>
          )}
        </div>
        {shouldShowBack && <div className="nav-spacer"></div>}
      </div>
    </nav>
  );
}

export default Navbar;
