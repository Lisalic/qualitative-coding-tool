import { useCallback, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../../api";

export default function useLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  // ProtectedRoute sends a signed-out visitor here with the page they
  // asked for; go back there after signing in, not always to Home.
  const fromPath = location.state?.from?.pathname || "/";
  const returnTo = fromPath === "/login" ? "/" : `${fromPath}${location.state?.from?.search || ""}`;

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      if (!email || !password) {
        setMessage("Enter your email and password.");
        setMessageType("error");
        return;
      }
      setSubmitting(true);
      setMessage("");

      try {
        const res = await api.post("/api/login/", { email, password });
        try {
          const token = res && res.data && res.data.access_token;
          if (token) {
            localStorage.setItem("access_token", token);
            api.defaults.headers.common.Authorization = `Bearer ${token}`;
          }
        } catch {
          // localStorage unavailable -- the cookie still carries the session.
        }

        setMessage("Login successful!");
        setMessageType("success");
        try {
          window.dispatchEvent(new Event("auth-changed"));
        } catch {
          // Non-browser environment -- nothing listening for the event.
        }
        navigate(returnTo, { replace: true });
      } catch (err) {
        const msg =
          (err &&
            err.response &&
            err.response.data &&
            err.response.data.detail) ||
          err.message ||
          "Login failed";
        setMessage(msg);
        setMessageType("error");
      } finally {
        setSubmitting(false);
      }
    },
    [email, navigate, password, returnTo],
  );

  return {
    email,
    setEmail,
    password,
    setPassword,
    submitting,
    message,
    messageType,
    handleSubmit,
  };
}
