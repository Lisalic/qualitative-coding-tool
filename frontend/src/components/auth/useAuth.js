import { useEffect, useState } from "react";
import { apiFetch } from "../../api";

export function useAuth() {
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let mounted = true;

    const checkAuth = () => {
      apiFetch("/api/me/")
        .then((response) => {
          if (!mounted) return;
          setStatus(response.ok ? "auth" : "unauth");
        })
        .catch(() => {
          if (!mounted) return;
          setStatus("unauth");
        });
    };

    checkAuth();

    const handleAuthChanged = () => {
      checkAuth();
    };

    window.addEventListener("auth-changed", handleAuthChanged);

    return () => {
      mounted = false;
      window.removeEventListener("auth-changed", handleAuthChanged);
    };
  }, []);

  return { status };
}
