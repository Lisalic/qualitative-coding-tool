import React from "react";
import { Link } from "react-router-dom";
import PageHeading from "../components/primitives/PageHeading";
import { btnPrimary } from "../lib/uiClasses";

const Landing = () => {
  return (
    <div className="flex h-full flex-col items-center justify-center overflow-y-auto gap-6 px-6 py-12 text-center">
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
          className={btnPrimary}
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
