import React from "react";
import { Link } from "react-router-dom";
import "../styles/Landing.css";

const Landing = () => {
  return (
    <div className="landing-container">
      <main className="landing-main">
        <h1 className="landing-title">Qualitative Coding Tool</h1>
        <section className="cta">
          <Link to="/login" className="btn btn-primary">
            Login
          </Link>
          <Link to="/register" className="btn btn-secondary">
            Register
          </Link>
        </section>
      </main>
    </div>
  );
};

export default Landing;
