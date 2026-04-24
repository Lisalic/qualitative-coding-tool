import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import React, { Suspense } from "react";
import ProtectedRoute from "./components/ProtectedRoute";
import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";
import AuthGate from "./components/AuthGate";
import "./App.css";

const ImportPage = React.lazy(() => import("./pages/Import"));
const Filter = React.lazy(() => import("./pages/Filter"));
const Data = React.lazy(() => import("./pages/Data"));
const FilteredData = React.lazy(() => import("./pages/FilteredData"));
const GenerateCodebook = React.lazy(() => import("./pages/GenerateCodebook"));
const ViewCodebook = React.lazy(() => import("./pages/ViewCodebook"));
const ApplyCodebook = React.lazy(() => import("./pages/ApplyCodebook"));
const ViewCoding = React.lazy(() => import("./pages/ViewCoding"));
const Project = React.lazy(() => import("./pages/Project"));
const CompareCodebook = React.lazy(
  () => import("./pages/CompareCodebook")
);
const CompareCoding = React.lazy(() => import("./pages/CompareCoding"));
const SummarizeCoding = React.lazy(
  () => import("./pages/SummarizeCoding")
);
const ViewSummary = React.lazy(() => import("./pages/ViewSummary"));
const Login = React.lazy(() => import("./pages/Login"));
const Register = React.lazy(() => import("./pages/Register"));

function App() {
  return (
    <Router>
      <div className="app-shell bg-base">
        <Navbar />
        <main className="app-shell__content">
          <Sidebar />
          <div className="app-shell__main">
            <Suspense
              fallback={
                <div className="route-loading">
                  <span>Loading...</span>
                </div>
              }
            >
              <Routes>
                <Route path="/" element={<AuthGate />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route
                  path="/import"
                  element={
                    <ProtectedRoute>
                      <ImportPage />
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
                  path="/project/:projectId"
                  element={
                    <ProtectedRoute>
                      <Project />
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
                  path="/compare-codebook"
                  element={
                    <ProtectedRoute>
                      <CompareCodebook />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/compare-coding"
                  element={
                    <ProtectedRoute>
                      <CompareCoding />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/summarize-coding"
                  element={
                    <ProtectedRoute>
                      <SummarizeCoding />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/summaryview"
                  element={
                    <ProtectedRoute>
                      <ViewSummary />
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
                <Route path="*" element={<AuthGate />} />
              </Routes>
            </Suspense>
          </div>
        </main>
      </div>
    </Router>
  );
}

export default App;
