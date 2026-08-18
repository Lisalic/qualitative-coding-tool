import React from "react";
import { Link } from "react-router-dom";
import PageHeading from "../components/primitives/PageHeading";

const Landing = () => {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 py-12 text-center">
      <PageHeading
        title="Qualitative Coding Tool"
        className="text-4xl font-bold sm:text-5xl"
      />
      <p className="max-w-md text-paper/70">
        Analyze, compare, and summarize qualitative coding projects in one place.
      </p>
      <section className="flex gap-4">
        <Link
          to="/login"
          className="border-2 border-paper px-6 py-3 font-semibold transition-colors hover:bg-paper hover:text-ink"
        >
          Login
        </Link>
        <Link
          to="/register"
          className="border border-paper px-6 py-3 transition-colors hover:bg-paper hover:text-ink"
        >
          Register
        </Link>
      </section>
    </div>
  );
};

export default Landing;
