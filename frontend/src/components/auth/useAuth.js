import { useEffect, useState } from "react";
import { apiFetch } from "../../api";

/**
 * One shared session check for the whole app.
 *
 * Navbar, Sidebar and the route guard all ask "am I signed in?", and each
 * used to run its own `GET /api/me/` -- three requests on every load and
 * three more on every `auth-changed` event, each a database lookup
 * server-side. The status now lives in one module-level store: the first
 * subscriber triggers the check, later ones read the same answer, and a
 * re-check in flight is shared rather than duplicated.
 */

let status = "loading";
let inFlight = null;
const listeners = new Set();

function publish(next) {
  if (next === status) return;
  status = next;
  listeners.forEach((listener) => listener(status));
}

function checkAuth() {
  if (inFlight) return inFlight;
  inFlight = apiFetch("/api/me/")
    .then((response) => {
      if (response.ok) {
        publish("auth");
      } else if (response.status === 401 || status === "loading") {
        // Only a 401 means "no session". A 5xx during a backend restart
        // used to sign the user out of the UI (and discard unsaved pages);
        // keep the last known answer unless there was none yet.
        publish("unauth");
      }
    })
    .catch(() => {
      if (status === "loading") publish("unauth");
    })
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}

if (typeof window !== "undefined") {
  window.addEventListener("auth-changed", () => {
    checkAuth();
  });
}

export function useAuth() {
  const [current, setCurrent] = useState(status);

  useEffect(() => {
    listeners.add(setCurrent);
    // The store may have moved on between render and subscribe.
    setCurrent(status);
    if (status === "loading") checkAuth();
    return () => {
      listeners.delete(setCurrent);
    };
  }, []);

  return { status: current };
}
