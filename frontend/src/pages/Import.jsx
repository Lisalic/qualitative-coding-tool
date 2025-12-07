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

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
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
        </div>
      </div>
    </>
  )
}