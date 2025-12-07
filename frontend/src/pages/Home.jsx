import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FileUpload from '../components/FileUpload'
import ErrorDisplay from '../components/ErrorDisplay'
import '../styles/Home.css'

export default function Home() {
  const [error, setError] = useState('')
  const [uploadData, setUploadData] = useState(null)
  const navigate = useNavigate()

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
    <div className="home-container">
      <div className="form-wrapper">
        <h1>Import Reddit Data</h1>
        
        <ErrorDisplay 
          message={error} 
          onDismiss={handleDismissError}
        />

        <FileUpload 
          onUploadSuccess={handleUploadSuccess}
          onError={handleUploadError}
        />

        <button onClick={handleViewData} className="view-data-btn">
          View Data
        </button>
      </div>
    </div>
  )
}
