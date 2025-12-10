import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import Navbar from '../components/Navbar'
import '../styles/Data.css'

export default function ViewCoding() {
  const navigate = useNavigate()
  const [report, setReport] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const handleBack = () => {
    navigate('/')
  }

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true)
        setError(null)

        const response = await fetch('/api/classification-report')
        if (!response.ok) {
          throw new Error('Failed to fetch classification report')
        }
        const data = await response.json()
        if (data.error) {
          setError(data.error)
        } else {
          setReport(data.classification_report)
        }
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchReport()
  }, [])

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
      <div className="data-container">
        <div style={{
          border: '1px solid #ffffff',
          borderRadius: '8px',
          padding: '20px',
          backgroundColor: '#000000'
        }}>
          <h1 style={{ textAlign: 'center', color: '#ffffff' }}>View Coding</h1>

          {loading && <p style={{ color: '#ffffff' }}>Loading classification report...</p>}
          {error && <div style={{color: '#ff6666', padding: '10px', border: '1px solid #ff6666', borderRadius: '4px', marginBottom: '20px'}}>{error}</div>}

          {report && (
            <div>
              <div style={{
                backgroundColor: '#000000',
                border: '1px solid #ffffff',
                borderRadius: '4px',
                padding: '20px',
                color: '#ffffff',
                maxHeight: '70vh',
                overflowY: 'auto'
              }}>
                <pre style={{ 
                  color: '#ffffff', 
                  whiteSpace: 'pre-wrap', 
                  fontFamily: 'monospace', 
                  fontSize: '14px',
                  margin: 0,
                  lineHeight: '1.5'
                }}>
                  {report}
                </pre>
              </div>
            </div>
          )}

          {!loading && !error && !report && (
            <p style={{ color: '#ffffff' }}>No classification report found. Please apply a codebook first.</p>
          )}
        </div>
      </div>
    </>
  )
}
