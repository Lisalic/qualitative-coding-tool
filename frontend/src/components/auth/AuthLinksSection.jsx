import { Link } from "react-router-dom";

export default function AuthLinksSection({ promptText, linkTo, linkLabel }) {
  return (
    <>
      <p>
        {promptText} <Link to={linkTo}>{linkLabel}</Link>
      </p>
      <p>
        <Link to="/">Back</Link>
      </p>
    </>
  );
}
