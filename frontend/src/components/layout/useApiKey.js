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
    try {
      const savedKey = localStorage.getItem("apiKey");
      if (savedKey) {
        setApiKey(savedKey);
      }
    } catch {
      // ignore storage errors
    }
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
    try {
      localStorage.setItem("apiKey", value);
    } catch {
      // ignore storage errors
    }
    setApiKey(value);
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
    sidebarCollapsed,
    toggleSidebar,
  };
}
