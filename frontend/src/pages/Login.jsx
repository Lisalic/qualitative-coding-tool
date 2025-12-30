import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "../styles/Auth.css";

const Login = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!email || !password) {
      setMessage("Please fill in all fields");
      setMessageType("error");
      return;
    }
    fetch("/api/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Login failed");
        }
        return res.json();
      })
      .then((data) => {
        setMessage("Login successful!");
        setMessageType("success");
        // notify other components (Navbar) that auth state changed
        try {
          window.dispatchEvent(new Event("auth-changed"));
        } catch (e) {}
        setTimeout(() => navigate("/home"), 500);
      })
      .catch((err) => {
        setMessage(err.message || "Login failed");
        setMessageType("error");
      });
  };

  return (
    <div className="auth-container">
      <h1 className="auth-title">Qualitative Coding Tool</h1>
      <div className="auth-card">
        <h2>Login</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Login
          </button>
        </form>
        {message && <p className={`${messageType}-message`}>{message}</p>}
        <p>
          Don't have an account? <Link to="/register">Register here</Link>
        </p>
        <p>
          <Link to="/">Back</Link>
        </p>
      </div>
    </div>
  );
};

export default Login;
