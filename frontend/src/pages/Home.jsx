import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import '../styles/Home.css'

export default function Home() {
  const navigate = useNavigate()

  const buttons = [
    { label: 'Import Data', path: '/import' },
    { label: 'View Data', path: '/data' },
    { label: 'Filter Data', path: '/filter' },
    { label: 'View Filtered Data', path: '/filtered-data' },
    { label: 'Generate Codebook', path: '/codebook-generate' },
    { label: 'View Codebook', path: '/codebook-view' },
    { label: 'Apply Codebook', path: '/codebook-apply' },
    { label: 'View Coding', path: '/coding-view' },
  ]

  const handleButtonClick = (path) => {
    navigate(path)
  }

  return (
    <>
      <Navbar showBack={false} />
      <div className="home-container">
        <div className="form-wrapper">
          <h1>Reddit Data Tool</h1>
          <div className="button-grid">
            {buttons.map((button, index) => (
              <button
                key={index}
                onClick={() => handleButtonClick(button.path)}
                className="main-button"
              >
                {button.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
