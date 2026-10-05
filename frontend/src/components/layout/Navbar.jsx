import { useNavigate } from "react-router-dom";
import { apiFetch, api } from "../../api";
import ToastService from "../feedback/ToastService";
import { useAuth } from "../auth/useAuth";
import { useApiKey } from "./useApiKey";
import BackButton from "./BackButton";
import { confirmLeave } from "../feedback/LeaveGuard";
import { btn } from "../../lib/uiClasses";

const iconBtn = `${btn} px-2.5`;
const ghostBtn = `${btn} text-xs sm:text-sm`;

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
    cancelApiKeyEdit,
    sidebarCollapsed,
    toggleSidebar,
  } = useApiKey();

  const handleSaveApiKey = (event) => {
    event.preventDefault();
    if (!apiKey.trim()) {
      ToastService.show("Enter your OpenRouter API key, or press Cancel.", "error");
      return;
    }
    saveApiKey(apiKey);
    ToastService.show("API key saved.", "success");
  };

  const leaveTo = async (to) => {
    if (await confirmLeave()) navigate(to);
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
            onClick={() => leaveTo("/")}
            className="text-lg font-medium transition-colors hover:text-paper/70"
          >
            Qualitative Coding Tool
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* The key is per account and used only by signed-in AI tools. */}
          {isAuth && showApiInput ? (
            <form
              onSubmit={handleSaveApiKey}
              onKeyDown={(e) => {
                if (e.key === "Escape") cancelApiKeyEdit();
              }}
              className="flex items-center gap-2"
            >
              <label htmlFor="navbar-api-key" className="text-xs text-paper/70">
                OpenRouter API key
              </label>
              <input
                id="navbar-api-key"
                type="password"
                autoComplete="off"
                autoFocus
                placeholder="sk-or-…"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-32 border border-paper bg-surface-raised px-2 py-1.5 text-sm text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper sm:w-40"
              />
              <button type="submit" className={ghostBtn}>
                Save
              </button>
              <button
                type="button"
                onClick={cancelApiKeyEdit}
                className="border border-paper/30 px-3 py-1.5 text-xs text-paper/70 transition-colors hover:bg-white/10 sm:text-sm"
              >
                Cancel
              </button>
            </form>
          ) : isAuth ? (
            <button
              type="button"
              onClick={() => setShowApiInput(true)}
              className={ghostBtn}
              title="Your OpenRouter API key, used for AI features"
            >
              {apiKey ? "API Key Set" : "Set API Key"}
            </button>
          ) : null}
          {isAuth ? (
            <button
              type="button"
              className={ghostBtn}
              onClick={async () => {
                if (!(await confirmLeave())) return;
                try {
                  await apiFetch("/api/logout/", { method: "POST" });
                } catch (e) {
                  // ignore
                }
                try {
                  localStorage.removeItem("access_token");
                  // The OpenRouter key is the account holder's (and billed
                  // to them); on a shared lab machine the next person
                  // must not inherit it.
                  localStorage.removeItem("apiKey");
                  delete api.defaults.headers.common["Authorization"];
                } catch {
                  // localStorage unavailable -- nothing stored to clear.
                }
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
