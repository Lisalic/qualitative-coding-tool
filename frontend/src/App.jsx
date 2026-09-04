import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import React, { Suspense } from "react";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import Sidebar from "./components/layout/Sidebar";
import Navbar from "./components/layout/Navbar";
import AuthGate from "./components/auth/AuthGate";

const ImportPage = React.lazy(() => import("./pages/Import"));
const Filter = React.lazy(() => import("./pages/Filter"));
const FilterEditor = React.lazy(() => import("./pages/FilterEditor"));
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
const ViewCodebookComparisons = React.lazy(
  () => import("./pages/ViewCodebookComparisons")
);
const ViewCodingComparisons = React.lazy(
  () => import("./pages/ViewCodingComparisons")
);
const Lineage = React.lazy(() => import("./pages/Lineage"));
const VersionHistory = React.lazy(() => import("./pages/VersionHistory"));
const Login = React.lazy(() => import("./pages/Login"));
const Register = React.lazy(() => import("./pages/Register"));

function App() {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      {/* Fixed-height app shell: the document never scrolls (see index.css),
          so every page owns its own scroll regions and a dense page can use
          the full viewport height without guessing at it with calc(). The
          `min-h-0` on <main> and the content column is load-bearing -- flex
          children default to min-height:auto and refuse to shrink below
          their content, which silently breaks every nested scroller.
          Page padding lives in PageShell, not here, so a full-bleed page
          can opt out of it entirely. */}
      <div className="flex h-dvh w-full flex-col overflow-hidden bg-ink text-paper">
        <Navbar />
        <main className="flex min-h-0 w-full flex-1 items-stretch">
          <Sidebar />
          <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <Suspense
              fallback={
                <div className="flex min-h-0 flex-1 items-center justify-center text-paper/70">
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
                  path="/filter-editor"
                  element={
                    <ProtectedRoute>
                      <FilterEditor />
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
                <Route
                  path="/codebook-comparison-view"
                  element={
                    <ProtectedRoute>
                      <ViewCodebookComparisons />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/coding-comparison-view"
                  element={
                    <ProtectedRoute>
                      <ViewCodingComparisons />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/lineage"
                  element={
                    <ProtectedRoute>
                      <Lineage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/versions"
                  element={
                    <ProtectedRoute>
                      <VersionHistory />
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
