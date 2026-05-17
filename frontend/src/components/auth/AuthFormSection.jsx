export default function AuthFormSection({
  mode,
  email,
  password,
  confirmPassword,
  onEmailChange,
  onPasswordChange,
  onConfirmPasswordChange,
  onSubmit,
}) {
  return (
    <div className="auth-card">
      <h2>{mode === "register" ? "Register" : "Login"}</h2>
      <form onSubmit={onSubmit}>
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            type="email"
            id="email"
            value={email}
            onChange={(event) => onEmailChange(event.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(event) => onPasswordChange(event.target.value)}
            required
          />
        </div>
        {mode === "register" ? (
          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(event) => onConfirmPasswordChange(event.target.value)}
              required
            />
          </div>
        ) : null}
        <button type="submit" className="btn btn-primary">
          {mode === "register" ? "Register" : "Login"}
        </button>
      </form>
    </div>
  );
}
