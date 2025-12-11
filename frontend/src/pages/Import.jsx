import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import FileUpload from '../components/FileUpload'
import ErrorDisplay from '../components/ErrorDisplay'
import { useState } from 'react'
import '../styles/Home.css'

export default function Import() {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [uploadData, setUploadData] = useState(null)

  const handleBack = () => {
    navigate('/')
  }

  const handleUploadSuccess = (data) => {
    setUploadData(data)
    setError('')
  }

  const handleUploadError = (errorMsg) => {
    setError(errorMsg)
    setUploadData(null)
  }

  const handleDismissError = () => {
    setError('')
  }

  const handleViewData = () => {
    navigate('/data')
  }

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
      <div className="home-container">
        <div className="form-wrapper">
          <h1>Import Data</h1>
          
          <div style={{ marginBottom: '30px', textAlign: 'center' }}>
            <button 
              onClick={handleViewData}
              style={{
                backgroundColor: '#000000',
                color: '#ffffff',
                border: '1px solid #ffffff',
                padding: '12px 24px',
                fontSize: '16px',
                cursor: 'pointer',
                borderRadius: '4px',
                transition: 'all 0.2s'
              }}
              onMouseOver={(e) => {
                e.target.style.backgroundColor = '#ffffff'
                e.target.style.color = '#000000'
              }}
              onMouseOut={(e) => {
                e.target.style.backgroundColor = '#000000'
                e.target.style.color = '#ffffff'
              }}
            >
              View Imported Data
            </button>
          </div>

          <ErrorDisplay
            message={error}
            onDismiss={handleDismissError}
          />
          <FileUpload
            onUploadSuccess={handleUploadSuccess}
            onError={handleUploadError}
          />
        </div>
      </div>
    </>
  )
}