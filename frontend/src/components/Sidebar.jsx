import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api";
import "../styles/Home.css";

export default function Sidebar() {
  const [isAuth, setIsAuth] = useState(null);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("sidebarCollapsed") === "true";
    } catch (e) {
      return false;
    }
  });
  const navigate = useNavigate();

  useEffect(() => {
    let mounted = true;
    const check = () => {
      apiFetch("/api/me/")
        .then((r) => {
          if (!mounted) return;
          setIsAuth(!!r.ok);
        })
        .catch(() => mounted && setIsAuth(false));
    };

    check();

    const handler = () => check();
    window.addEventListener("auth-changed", handler);
    return () => {
      mounted = false;
      window.removeEventListener("auth-changed", handler);
    };
  }, []);

  useEffect(() => {
    const handler = () => {
      try {
        setCollapsed(localStorage.getItem("sidebarCollapsed") === "true");
      } catch (e) {}
    };
    window.addEventListener("sidebar-toggle", handler);
    return () => window.removeEventListener("sidebar-toggle", handler);
  }, []);

  if (isAuth === null) return null;

  const authButtons = [
    ["Home", "/"],
    ["Import Data", "/import"],
    ["View Data", "/data"],
    ["Filter Data", "/filter"],
    ["View Filtered Data", "/filtered-data"],
    ["Generate Codebook", "/codebook-generate"],
    ["View Codebook", "/codebook-view"],
    ["Apply Codebook", "/codebook-apply"],
    ["View Coding", "/coding-view"],
  ];

  const anonButtons = [
    ["Login", "/login"],
    ["Register", "/register"],
  ];

  const items = isAuth ? authButtons : anonButtons;

  if (collapsed) return null;

  return (
    <aside className="app-sidebar">
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          className="sidebar-close"
          aria-label="Collapse sidebar"
          onClick={() => {
            setCollapsed(true);
            try {
              localStorage.setItem("sidebarCollapsed", "true");
              // notify navbar and other listeners
              window.dispatchEvent(new Event("sidebar-toggle"));
            } catch (e) {}
          }}
        >
          ✕
        </button>
      </div>

      {items.map(([label, path]) => (
        <button
          key={path}
          className="sidebar-btn"
          onClick={() => navigate(path)}
        >
          {label}
        </button>
      ))}
    </aside>
  );
}
