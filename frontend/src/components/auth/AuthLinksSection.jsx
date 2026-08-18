import { Link } from "react-router-dom";

const linkClasses = "text-paper underline underline-offset-2 hover:text-paper/70";

export default function AuthLinksSection({ promptText, linkTo, linkLabel }) {
  return (
    <div className="flex flex-col items-center gap-2 text-sm text-paper/80">
      <p>
        {promptText}{" "}
        <Link to={linkTo} className={linkClasses}>
          {linkLabel}
        </Link>
      </p>
      <p>
        <Link to="/" className={linkClasses}>
          Back
        </Link>
      </p>
    </div>
  );
}
