import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import '../styles/Home.css'

export default function Home() {
  const navigate = useNavigate()

  const handleImportClick = () => {
    navigate('/import')
  }

  const handleViewClick = () => {
    navigate('/data')
  }

  const handleFilterClick = () => {
    navigate('/filter')
  }

  return (
    <>
      <Navbar showBack={false} />
      <div className="home-container">
        <div className="form-wrapper">
          <h1>Reddit Data Tool</h1>
          <div className="button-grid">
            <button onClick={handleImportClick} className="main-button">
              Import Data
            </button>
            <button onClick={handleViewClick} className="main-button">
              View Data
            </button>
            <button onClick={handleFilterClick} className="main-button">
              Filter Data
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
