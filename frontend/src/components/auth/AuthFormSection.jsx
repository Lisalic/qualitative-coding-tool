const TITLES = {
  login: "Login",
  register: "Register",
  forgot: "Reset Password",
  reset: "Choose a New Password",
};

const SUBMIT_LABELS = {
  login: "Login",
  register: "Register",
  forgot: "Send Reset Link",
  reset: "Update Password",
};

const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper";

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
}) {
  const showEmail = mode !== "reset";
  const showPassword = mode !== "forgot";
  const showConfirm = mode === "register" || mode === "reset";

  return (
    <div className="w-full max-w-sm border-2 border-paper p-8">
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
              {mode === "reset" ? "New Password" : "Password"}
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              required
              className={inputClasses}
            />
          </div>
        ) : null}
        {showConfirm ? (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="confirmPassword" className="text-sm">
              Confirm Password
            </label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(event) => onConfirmPasswordChange(event.target.value)}
              required
              className={inputClasses}
            />
          </div>
        ) : null}
        <button
          type="submit"
          disabled={disabled}
          className="mt-2 border-2 border-paper px-6 py-2.5 text-base font-semibold transition-colors hover:bg-paper hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
        >
          {SUBMIT_LABELS[mode]}
        </button>
      </form>
    </div>
  );
}
