import React, { useEffect, useState } from "react";
import { apiFetch } from "../api";
import Landing from "../pages/Landing";
const Home = React.lazy(() => import("../pages/Home"));

const AuthGate = () => {
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let mounted = true;

    const check = () => {
      apiFetch("/api/me/")
        .then((r) => {
          if (!mounted) return;
          setStatus(r.ok ? "auth" : "unauth");
        })
        .catch(() => {
          if (!mounted) return;
          setStatus("unauth");
        });
    };

    check();

    const handler = () => {
      check();
    };

    window.addEventListener("auth-changed", handler);

    return () => {
      mounted = false;
      window.removeEventListener("auth-changed", handler);
    };
  }, []);

  if (status === "loading") {
    return (
      <div className="route-loading">
        <span>Loading...</span>
      </div>
    );
  }

  return status === "auth" ? <Home /> : <Landing />;
};

export default AuthGate;

