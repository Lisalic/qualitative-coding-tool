import { useEffect, useState } from "react";
import { apiFetch } from "../../api/client";

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
// Bumped on every `auth-changed`: a check sent with the previous
// credentials must not decide the status once they have changed.
let generation = 0;
const listeners = new Set();

function publish(next) {
  if (next === status) return;
  status = next;
  listeners.forEach((listener) => listener(status));
}

function checkAuth() {
  if (inFlight) return inFlight;
  const gen = generation;
  const request = apiFetch("/api/me/")
    .then((response) => {
      if (gen !== generation) return;
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
      if (gen !== generation) return;
      if (status === "loading") publish("unauth");
    })
    .finally(() => {
      if (inFlight === request) inFlight = null;
    });
  inFlight = request;
  return request;
}

if (typeof window !== "undefined") {
  window.addEventListener("auth-changed", () => {
    generation += 1;
    inFlight = null;
    // A login navigates straight to a guarded page: left at "unauth" until
    // this check lands, the guard would bounce it back to /login. "loading"
    // makes it wait. A signed-in session keeps "auth" until the check says
    // otherwise, so logging out doesn't flash a loading screen.
    if (status !== "auth") publish("loading");
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
