import { useCallback, useState } from "react";
import { requestJson } from "../../api";

export default function useForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      if (!email) {
        setMessage("Please enter your email");
        setMessageType("error");
        return;
      }

      setSubmitting(true);
      const res = await requestJson("/api/forgot-password/", { body: { email } });
      setSubmitting(false);
      if (res.ok) {
        setMessage(`${res.data.message} Check your inbox (and spam folder).`);
        setMessageType("success");
      } else {
        setMessage(res.error || "Could not send reset link");
        setMessageType("error");
      }
    },
    [email],
  );

  return { email, setEmail, message, messageType, submitting, handleSubmit };
}
