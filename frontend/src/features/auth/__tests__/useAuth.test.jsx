// @vitest-environment jsdom
import { expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";

// `/api/me/` answers with whatever the session was when the request went
// out, after a real-network-sized delay -- an instant mock resolves before
// React renders and hides the race this file guards against.
let signedIn = false;
let delayMs = 30;
vi.mock("../../../api/client", () => ({
  apiFetch: vi.fn(() => {
    const ok = signedIn;
    const ms = delayMs;
    return new Promise((resolve) => setTimeout(() => resolve({ ok, status: ok ? 200 : 401 }), ms));
  }),
}));
const { default: ProtectedRoute } = await import("../ProtectedRoute");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let navigate;
function LoginPage() {
  navigate = useNavigate();
  return <p>login page</p>;
}

it("lands on the guarded page after logging in from a /login bounce", async () => {
  const container = document.createElement("div");
  const root = createRoot(container);
  await act(async () =>
    root.render(
      <MemoryRouter initialEntries={["/codebook"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/codebook"
            element={
              <ProtectedRoute>
                <p>codebook page</p>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    ),
  );
  await act(() => wait(60));
  expect(container.textContent).toBe("login page");

  // A slow check sent with the OLD (anonymous) session is still in flight
  // when the login lands; it must not decide the status afterwards.
  delayMs = 80;
  await act(async () => window.dispatchEvent(new Event("auth-changed")));
  delayMs = 30;

  // What useLoginPage does on success: store the session, announce it,
  // navigate straight back to where the user came from.
  signedIn = true;
  await act(async () => {
    window.dispatchEvent(new Event("auth-changed"));
    navigate("/codebook", { replace: true });
  });
  await act(() => wait(150));
  expect(container.textContent).toBe("codebook page");

  act(() => root.unmount());
});
