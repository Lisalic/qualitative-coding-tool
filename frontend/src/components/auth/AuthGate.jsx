import React from "react";
import Landing from "../../pages/Landing";
import { useAuth } from "./useAuth";
const Home = React.lazy(() => import("../../pages/Home"));

const AuthGate = () => {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center text-paper/70">
        <span>Loading...</span>
      </div>
    );
  }

  return status === "auth" ? <Home /> : <Landing />;
};

export default AuthGate;

