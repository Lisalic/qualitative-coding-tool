import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Import from './pages/Import'
import Filter from './pages/Filter'
import Data from './pages/Data'
import './App.css'

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/import" element={<Import />} />
          <Route path="/filter" element={<Filter />} />
          <Route path="/data" element={<Data />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
