import React from "react";
import { Link } from "react-router-dom";
import PageHeading from "../components/primitives/PageHeading";
import "../styles/Landing.css";

const Landing = () => {
  return (
    <div className="landing-container">
      <main className="landing-main">
        <PageHeading title="Qualitative Coding Tool" className="landing-title" />
        <p className="text-muted" style={{ textAlign: "center", maxWidth: 560 }}>
          Analyze, compare, and summarize qualitative coding projects in one place.
        </p>
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
