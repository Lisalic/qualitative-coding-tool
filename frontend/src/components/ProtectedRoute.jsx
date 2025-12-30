import React, { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

const ProtectedRoute = ({ children }) => {
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let mounted = true;
    fetch("/api/me/", { credentials: "include" })
      .then((res) => {
        if (!mounted) return;
        if (res.ok) setStatus("ok");
        else setStatus("unauth");
      })
      .catch(() => mounted && setStatus("unauth"));
    return () => {
      mounted = false;
    };
  }, []);

  if (status === "loading") return null;
  if (status === "unauth") return <Navigate to="/" replace />;
  return children;
};

export default ProtectedRoute;
