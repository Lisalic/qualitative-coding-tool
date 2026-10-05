import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { MIN_PASSWORD_LENGTH } from "../../lib/apiContracts";

export default function useRegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      if (!email || !password || !confirmPassword) {
        setMessage("Fill in every field.");
        setMessageType("error");
        return;
      }
      if (password !== confirmPassword) {
        setMessage("The two passwords don't match.");
        setMessageType("error");
        return;
      }
      if (password.length < MIN_PASSWORD_LENGTH) {
        setMessage(`Use a password of at least ${MIN_PASSWORD_LENGTH} characters.`);
        setMessageType("error");
        return;
      }
      setSubmitting(true);
      setMessage("");

      try {
        const res = await api.post("/api/register/", { email, password });
        try {
          const token = res && res.data && res.data.access_token;
          if (token) {
            localStorage.setItem("access_token", token);
            api.defaults.headers.common.Authorization = `Bearer ${token}`;
          }
        } catch {
          // localStorage unavailable -- the cookie still carries the session.
        }

        setMessage("Registration successful!");
        setMessageType("success");
        try {
          window.dispatchEvent(new Event("auth-changed"));
        } catch {
          // Non-browser environment -- nothing listening for the event.
        }
        navigate("/", { replace: true });
      } catch (err) {
        const msg =
          (err &&
            err.response &&
            err.response.data &&
            err.response.data.detail) ||
          err.message ||
          "Registration failed";
        setMessage(msg);
        setMessageType("error");
      } finally {
        setSubmitting(false);
      }
    },
    [confirmPassword, email, navigate, password],
  );

  return {
    email,
    setEmail,
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
