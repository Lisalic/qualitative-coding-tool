import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { requestJson } from "../../api/client";
import { MIN_PASSWORD_LENGTH } from "../../api/contracts";

export default function useResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState(
    token ? "" : "This reset link is missing its token. Request a new one.",
  );
  const [messageType, setMessageType] = useState(token ? "" : "error");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  // The post-success redirect is cancelled on unmount, so leaving the page
  // within the delay doesn't yank the user to /login from wherever they went.
  const redirectTimer = useRef(null);
  useEffect(() => () => clearTimeout(redirectTimer.current), []);

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      if (!password || !confirmPassword) {
        setMessage("Please fill in all fields");
        setMessageType("error");
        return;
      }
      if (password !== confirmPassword) {
        setMessage("Passwords do not match");
        setMessageType("error");
        return;
      }
      if (password.length < MIN_PASSWORD_LENGTH) {
        setMessage(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`);
        setMessageType("error");
        return;
      }

      setSubmitting(true);
      const res = await requestJson("/api/reset-password/", {
        body: { token, new_password: password },
      });
      setSubmitting(false);
      if (res.ok) {
        setMessage(res.data.message);
        setMessageType("success");
        redirectTimer.current = setTimeout(() => navigate("/login"), 1500);
      } else {
        setMessage(res.error || "Could not reset password");
        setMessageType("error");
      }
    },
    [confirmPassword, navigate, password, token],
  );

  return {
    token,
    password,
    setPassword,
    confirmPassword,
    setConfirmPassword,
    message,
    messageType,
    submitting,
    handleSubmit,
  };
}
