import React from "react";
import { Link } from "react-router-dom";
import PageHeading from "../components/primitives/PageHeading";
import { btn, btnPrimary } from "../lib/uiClasses";

const Landing = () => {
  return (
    <div className="flex h-full flex-col items-center justify-center overflow-y-auto gap-6 px-6 py-12 text-center">
      <PageHeading
        title="Qualitative Coding Tool"
        className="text-4xl font-bold sm:text-5xl"
      />
      <section className="flex gap-4">
        {/* Same box for both, so the pair lines up; the primary one is
            set apart by weight and its 2px border alone. */}
        <Link to="/login" className={`${btnPrimary} px-6 py-2.5 text-base hover:text-ink`}>
          Log in
        </Link>
        <Link to="/register" className={`${btn} px-6 py-2.5 text-base hover:text-ink`}>
          Register
        </Link>
      </section>
    </div>
  );
};

export default Landing;
