import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

const btnClasses =
  "border border-paper px-2.5 py-1.5 text-sm hover:bg-paper hover:text-ink transition-colors";

/**
 * Global "back" affordance, rendered in the Navbar so it's available on
 * every page (including outside `<Routes>`, matching Navbar's own
 * placement). Uses `navigate(-1)` rather than a fixed destination so it
 * restores the previous entry's `location.state` -- most pages carry
 * their selection there (`/data`, `/coding-view`, `/codebook-view`,
 * etc.), so a plain "go to parent route" link would drop that context.
 *
 * react-router v6's `BrowserRouter` stamps `history.state.idx` on every
 * entry; `idx > 0` means there's an in-app entry behind the current one,
 * so `navigate(-1)` won't leave the app onto whatever page (or nothing)
 * was open before this tab loaded. Hidden entirely on a cold entry
 * (`idx === 0`) rather than shown disabled, so it's never a dead control.
 */
export default function BackButton() {
  const navigate = useNavigate();
  const location = useLocation();
  const [canGoBack, setCanGoBack] = useState(false);

  useEffect(() => {
    setCanGoBack((window.history.state?.idx ?? 0) > 0);
  }, [location.key]);

  if (!canGoBack) return null;

  return (
    <button
      type="button"
      className={btnClasses}
      aria-label="Go back"
      onClick={() => navigate(-1)}
    >
      &lsaquo; Back
    </button>
  );
}
