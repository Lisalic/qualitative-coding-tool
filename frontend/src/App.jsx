import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
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
import Login from "./pages/Login";
import Register from "./pages/Register";
import "./App.css";

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/home" element={<Home />} />
          <Route path="/import" element={<Import />} />
          <Route path="/data" element={<Data />} />
          <Route path="/filter" element={<Filter />} />
          <Route path="/filtered-data" element={<FilteredData />} />
          <Route path="/codebook-generate" element={<GenerateCodebook />} />
          <Route path="/codebook-view" element={<ViewCodebook />} />
          <Route path="/codebook-apply" element={<ApplyCodebook />} />
          <Route path="/coding-view" element={<ViewCoding />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
