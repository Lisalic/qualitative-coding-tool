import './Navbar.css'

function Navbar({ showBack, onBack }) {
  return (
    <nav className="navbar">
      <div className={`navbar-container ${showBack ? 'navbar-with-back' : 'navbar-centered'}`}>
        {showBack && (
          <button className="navbar-back-button" onClick={onBack}>
            ← Back
          </button>
        )}
        <div className="navbar-brand">
          Qualitative Coding Tool
        </div>
        {showBack && <div className="navbar-spacer"></div>}
      </div>
    </nav>
  )
}

export default Navbar
