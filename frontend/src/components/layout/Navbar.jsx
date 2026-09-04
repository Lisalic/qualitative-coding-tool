import { useNavigate } from "react-router-dom";
import { apiFetch, api } from "../../api";
import ToastService from "../feedback/ToastService";
import { useAuth } from "../auth/useAuth";
import { useApiKey } from "./useApiKey";
import BackButton from "./BackButton";

const iconBtn =
  "border border-paper px-2.5 py-1.5 text-sm hover:bg-paper hover:text-ink transition-colors";
const ghostBtn =
  "border border-paper px-3 py-1.5 text-xs sm:text-sm hover:bg-paper hover:text-ink transition-colors";

function Navbar() {
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

  return (
    <nav className="sticky top-0 z-50 border-b border-paper bg-ink px-4 py-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            type="button"
            className={iconBtn}
            aria-label="Toggle sidebar"
            aria-expanded={!sidebarCollapsed}
            onClick={toggleSidebar}
          >
            ☰
          </button>
          <BackButton />
          <button
            type="button"
            onClick={() => navigate("/")}
            className="text-lg font-medium transition-colors hover:text-paper/70"
          >
            Qualitative Coding Tool
          </button>
        </div>

        <div className="flex items-center gap-2">
          {showApiInput ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-paper/70">API Key</span>
              <input
                type="password"
                placeholder="Enter API Key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-40 border border-paper bg-white/5 px-2 py-1.5 text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper"
              />
              <button type="button" onClick={handleSaveApiKey} className={ghostBtn}>
                Save
              </button>
              <button
                type="button"
                onClick={() => setShowApiInput(false)}
                className="border border-paper/30 px-3 py-1.5 text-xs text-paper/70 transition-colors hover:bg-white/10 sm:text-sm"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowApiInput(true)}
              className={ghostBtn}
            >
              {apiKey ? "API Key Set" : "Set API Key"}
            </button>
          )}
          {isAuth ? (
            <button
              type="button"
              className={ghostBtn}
              onClick={async () => {
                try {
                  await apiFetch("/api/logout/", { method: "POST" });
                } catch (e) {
                  // ignore
                }
                try {
                  localStorage.removeItem("access_token");
                  delete api.defaults.headers.common["Authorization"];
                } catch (e) {}
                window.dispatchEvent(new Event("auth-changed"));
                navigate("/");
              }}
            >
              Logout
            </button>
          ) : (
            <button
              type="button"
              className={ghostBtn}
              onClick={() => {
                navigate("/login");
              }}
            >
              Log in
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
