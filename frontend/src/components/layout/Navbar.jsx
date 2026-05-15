import { useLocation, useNavigate } from "react-router-dom";
import { apiFetch, api } from "../../api";
import ToastService from "../feedback/ToastService";
import { useAuth } from "../auth/useAuth";
import { useApiKey } from "./useApiKey";
import "./Navbar.css";

function Navbar({ showBack, onBack }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { status } = useAuth();
  const isAuth = status === "auth";
  const {
    apiKey,
    setApiKey,
    showApiInput,
    setShowApiInput,
    saveApiKey,
    sidebarCollapsed,
    toggleSidebar,
  } = useApiKey();

  const handleSaveApiKey = () => {
    saveApiKey(apiKey);
    ToastService.show("API Key saved!", "success");
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
          aria-expanded={!sidebarCollapsed}
          onClick={toggleSidebar}
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
              <span className="nav-api-label">API Key</span>
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
