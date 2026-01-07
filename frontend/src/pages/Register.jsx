import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "../styles/Auth.css";
import { api } from "../api";

const Register = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!email || !password || !confirmPassword) {
      setMessage("Please fill in all fields");
      setMessageType("error");
      return;
    }

    if (password !== confirmPassword) {
      setMessage("Passwords do not match");
      setMessageType("error");
      return;
    }

    try {
      const res = await api.post("/api/register/", { email, password });
      setMessage("Registration successful!");
      setMessageType("success");
      try {
        window.dispatchEvent(new Event("auth-changed"));
      } catch (e) {}
      setTimeout(() => navigate("/home"), 1000);
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
    }
  };

  return (
    <div className="auth-container">
      <h1 className="auth-title">Qualitative Coding Tool</h1>
      <div className="auth-card">
        <h2>Register</h2>
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
          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Register
          </button>
        </form>
        {message && <p className={`${messageType}-message`}>{message}</p>}
        <p>
          Already have an account? <Link to="/login">Login here</Link>
        </p>
        <p>
          <Link to="/">Back</Link>
        </p>
      </div>
    </div>
  );
};

export default Register;
