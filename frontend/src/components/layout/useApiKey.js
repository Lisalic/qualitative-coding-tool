import { useEffect, useState } from "react";

export function useApiKey() {
  const [apiKey, setApiKey] = useState("");
  const [showApiInput, setShowApiInput] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      const stored = localStorage.getItem("sidebarCollapsed");
      if (stored !== null) return stored === "true";
      return typeof window !== "undefined" && window.innerWidth < 768;
    } catch {
      return false;
    }
  });

  useEffect(() => {
    // Re-read on login/logout too: logout clears the stored key.
    const loadKey = () => {
      try {
        setApiKey(localStorage.getItem("apiKey") || "");
      } catch {
        // ignore storage errors
      }
    };
    loadKey();
    window.addEventListener("auth-changed", loadKey);
    return () => window.removeEventListener("auth-changed", loadKey);
  }, []);

  useEffect(() => {
    const handleSidebarToggle = () => {
      try {
        setSidebarCollapsed(localStorage.getItem("sidebarCollapsed") === "true");
      } catch {
        setSidebarCollapsed(false);
      }
    };

    window.addEventListener("sidebar-toggle", handleSidebarToggle);
    return () => window.removeEventListener("sidebar-toggle", handleSidebarToggle);
  }, []);

  const saveApiKey = (value) => {
    const trimmed = String(value || "").trim();
    try {
      localStorage.setItem("apiKey", trimmed);
    } catch {
      // ignore storage errors
    }
    setApiKey(trimmed);
    setShowApiInput(false);
  };

  // Cancel discards whatever was typed: the field shares state with the
  // "API Key Set" button label, which must reflect what's actually stored.
  const cancelApiKeyEdit = () => {
    try {
      setApiKey(localStorage.getItem("apiKey") || "");
    } catch {
      setApiKey("");
    }
    setShowApiInput(false);
  };

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("sidebarCollapsed", String(next));
      } catch {
        // ignore storage errors
      }
      window.dispatchEvent(new Event("sidebar-toggle"));
      return next;
    });
  };

  return {
    apiKey,
    setApiKey,
    showApiInput,
    setShowApiInput,
    saveApiKey,
    cancelApiKeyEdit,
    sidebarCollapsed,
    toggleSidebar,
  };
}
