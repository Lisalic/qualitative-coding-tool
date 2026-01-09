import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import React, { useEffect, useState } from "react";
import Home from "./pages/Home";
import Import from "./pages/Import";
import Filter from "./pages/Filter";
import Data from "./pages/Data";
import FilteredData from "./pages/FilteredData";
import GenerateCodebook from "./pages/GenerateCodebook";
import ViewCodebook from "./pages/ViewCodebook";
import ApplyCodebook from "./pages/ApplyCodebook";
import ViewCoding from "./pages/ViewCoding";
import Landing from "./pages/Landing";
import { apiFetch } from "./api";
import Login from "./pages/Login";
import Register from "./pages/Register";
import ProtectedRoute from "./components/ProtectedRoute";
import "./App.css";

function App() {
  const AuthGate = () => {
    const [status, setStatus] = useState("loading");

    useEffect(() => {
      let mounted = true;
      const check = () => {
        apiFetch("/api/me/")
          .then((r) => {
            if (!mounted) return;
            setStatus(r.ok ? "auth" : "unauth");
          })
          .catch(() => mounted && setStatus("unauth"));
      };

      check();

      const handler = () => {
        check();
      };

      window.addEventListener("auth-changed", handler);

      return () => {
        mounted = false;
        window.removeEventListener("auth-changed", handler);
      };
    }, []);

    if (status === "loading") return null;
    return status === "auth" ? <Home /> : <Landing />;
  };

  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<AuthGate />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/import"
            element={
              <ProtectedRoute>
                <Import />
              </ProtectedRoute>
            }
          />
          <Route
            path="/data"
            element={
              <ProtectedRoute>
                <Data />
              </ProtectedRoute>
            }
          />
          <Route
            path="/filter"
            element={
              <ProtectedRoute>
                <Filter />
              </ProtectedRoute>
            }
          />
          <Route
            path="/filtered-data"
            element={
              <ProtectedRoute>
                <FilteredData />
              </ProtectedRoute>
            }
          />
          <Route
            path="/codebook-generate"
            element={
              <ProtectedRoute>
                <GenerateCodebook />
              </ProtectedRoute>
            }
          />
          <Route
            path="/codebook-view"
            element={
              <ProtectedRoute>
                <ViewCodebook />
              </ProtectedRoute>
            }
          />
          <Route
            path="/codebook-apply"
            element={
              <ProtectedRoute>
                <ApplyCodebook />
              </ProtectedRoute>
            }
          />
          <Route
            path="/coding-view"
            element={
              <ProtectedRoute>
                <ViewCoding />
              </ProtectedRoute>
            }
          />
          {/* Catch-all: render AuthGate to show Home or Landing based on auth */}
          <Route path="*" element={<AuthGate />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
