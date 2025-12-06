import { useState } from 'react'
import FileUpload from '../components/FileUpload'
import DataTable from '../components/DataTable'
import ErrorDisplay from '../components/ErrorDisplay'
import '../styles/Home.css'

export default function Home() {
  const [error, setError] = useState('')
  const [uploadData, setUploadData] = useState(null)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const handleUploadSuccess = (data) => {
    console.log('[Home] Upload successful:', data)
    setUploadData(data)
    setError('')
    setRefreshTrigger(prev => prev + 1)
  }

  const handleUploadError = (errorMsg) => {
    console.error('[Home] Upload error:', errorMsg)
    setError(errorMsg)
    setUploadData(null)
  }

  const handleDismissError = () => {
    setError('')
  }

  return (
    <div className="home-container">
      <div className="form-wrapper">
        <h1>Import Reddit Data</h1>
        
        <ErrorDisplay 
          message={error} 
          onDismiss={handleDismissError}
        />

        {!uploadData ? (
          <FileUpload 
            onUploadSuccess={handleUploadSuccess}
            onError={handleUploadError}
          />
        ) : (
          <DataTable key={refreshTrigger} />
        )}
      </div>
    </div>
  )
}
