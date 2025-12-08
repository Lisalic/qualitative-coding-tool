import { useLocation, useNavigate } from 'react-router-dom'
import './Navbar.css'

function Navbar({ showBack, onBack }) {
  const location = useLocation()
  const navigate = useNavigate()

  const shouldShowBack = showBack !== undefined ? showBack : location.pathname !== '/'

  const handleBack = onBack || (() => navigate(-1))

  return (
    <nav className="navbar">
      <div className={`navbar-container ${shouldShowBack ? 'navbar-with-back' : 'navbar-centered'}`}>
        {shouldShowBack && (
          <button className="navbar-back-button" onClick={handleBack}>
            ← Back
          </button>
        )}
        <div className="navbar-brand">
          Qualitative Coding Tool
        </div>
        {shouldShowBack && <div className="navbar-spacer"></div>}
      </div>
    </nav>
  )
}

export default Navbar
