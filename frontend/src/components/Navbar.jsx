import { useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { apiFetch } from "../api";
import "./Navbar.css";

function Navbar({ showBack, onBack }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [apiKey, setApiKey] = useState("");
  const [showApiInput, setShowApiInput] = useState(false);
  const [isAuth, setIsAuth] = useState(false);

  useEffect(() => {
    const savedKey = localStorage.getItem("apiKey");
    if (savedKey) {
      setApiKey(savedKey);
    }
    // Check authentication status
    apiFetch("/api/me/")
      .then((r) => {
        if (r.ok) setIsAuth(true);
        else setIsAuth(false);
      })
      .catch(() => setIsAuth(false));
    // Listen for global auth changes (login/register/logout)
    const handler = () => {
      apiFetch("/api/me/")
        .then((r) => {
          if (r.ok) setIsAuth(true);
          else setIsAuth(false);
        })
        .catch(() => setIsAuth(false));
    };
    window.addEventListener("auth-changed", handler);
    return () => window.removeEventListener("auth-changed", handler);
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
    <nav className="navbar">
      <div className="navbar-container">
        {shouldShowBack && (
          <button className="navbar-back-button" onClick={handleBack}>
            ← Back
          </button>
        )}
        <div className="navbar-brand">Qualitative Coding Tool</div>
        <div className="navbar-api">
          {showApiInput ? (
            <div className="api-input-group">
              <input
                type="password"
                placeholder="Enter API Key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="api-input"
              />
              <button onClick={handleSaveApiKey} className="api-save-btn">
                Save
              </button>
              <button
                onClick={() => setShowApiInput(false)}
                className="api-cancel-btn"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowApiInput(true)}
              className="api-toggle-btn"
            >
              {apiKey ? "API Key Set" : "Set API Key"}
            </button>
          )}
          {isAuth ? (
            <button
              className="logout-btn"
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
              className="login-btn"
              onClick={() => {
                navigate("/login");
              }}
            >
              Log in
            </button>
          )}
        </div>
        {shouldShowBack && <div className="navbar-spacer"></div>}
      </div>
    </nav>
  );
}

export default Navbar;
