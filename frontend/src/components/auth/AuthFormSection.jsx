import ErrorDisplay from "../feedback/ErrorDisplay";
import { MIN_PASSWORD_LENGTH } from "../../lib/apiContracts";
import { btnPrimary, input, meta } from "../../lib/uiClasses";

const TITLES = {
  login: "Log in",
  register: "Register",
  forgot: "Forgot password",
  reset: "Choose a new password",
};

const SUBMIT_LABELS = {
  login: "Log in",
  register: "Register",
  forgot: "Send reset link",
  reset: "Update password",
};

const BUSY_LABELS = {
  login: "Logging in…",
  register: "Registering…",
  forgot: "Sending…",
  reset: "Updating…",
};

const inputClasses = `${input} py-2.5 text-base`;

export default function AuthFormSection({
  mode,
  email,
  password,
  confirmPassword,
  onEmailChange,
  onPasswordChange,
  onConfirmPasswordChange,
  onSubmit,
  disabled = false,
  busy = false,
  message = "",
  messageType = "",
}) {
  const showEmail = mode !== "reset";
  const showPassword = mode !== "forgot";
  const showConfirm = mode === "register" || mode === "reset";

  return (
    <div className="w-full max-w-sm border border-line bg-surface p-8">
      <h2 className="mb-6 text-center text-xl font-semibold">
        {TITLES[mode]}
      </h2>
      <form onSubmit={onSubmit} className="flex flex-col gap-5">
        {showEmail ? (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className="text-sm">
              Email
            </label>
            <input
              type="email"
              id="email"
              autoComplete="email"
              value={email}
              onChange={(event) => onEmailChange(event.target.value)}
              required
              className={inputClasses}
            />
          </div>
        ) : null}
        {showPassword ? (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className="text-sm">
              {mode === "reset" ? "New password" : "Password"}
            </label>
            <input
              type="password"
              id="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              aria-describedby={showConfirm ? "passwordHint" : undefined}
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              required
              className={inputClasses}
            />
            {showConfirm ? (
              <p id="passwordHint" className={meta}>
                At least {MIN_PASSWORD_LENGTH} characters.
              </p>
            ) : null}
          </div>
        ) : null}
        {showConfirm ? (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="confirmPassword" className="text-sm">
              Confirm password
            </label>
            <input
              type="password"
              id="confirmPassword"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => onConfirmPasswordChange(event.target.value)}
              required
              className={inputClasses}
            />
          </div>
        ) : null}
        <button
          type="submit"
          disabled={disabled || busy}
          className={`${btnPrimary} mt-2 py-2.5 text-base disabled:cursor-not-allowed`}
        >
          {busy ? BUSY_LABELS[mode] : SUBMIT_LABELS[mode]}
        </button>
        {/* The result sits right under the button that produced it. */}
        <ErrorDisplay message={message} type={messageType || "error"} variant="message" />
      </form>
    </div>
  );
}
