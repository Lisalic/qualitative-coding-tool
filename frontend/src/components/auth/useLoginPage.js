import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";

export default function useLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");
  const navigate = useNavigate();

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      if (!email || !password) {
        setMessage("Please fill in all fields");
        setMessageType("error");
        return;
      }

      try {
        const res = await api.post("/api/login/", { email, password });
        try {
          const token = res && res.data && res.data.access_token;
          if (token) {
            localStorage.setItem("access_token", token);
            api.defaults.headers.common.Authorization = `Bearer ${token}`;
          }
        } catch (error) {}

        setMessage("Login successful!");
        setMessageType("success");
        try {
          window.dispatchEvent(new Event("auth-changed"));
        } catch (error) {}
        setTimeout(() => navigate("/"), 500);
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
      }
    },
    [email, navigate, password],
  );

  return {
    email,
    setEmail,
    password,
    setPassword,
    message,
    messageType,
    handleSubmit,
  };
}
