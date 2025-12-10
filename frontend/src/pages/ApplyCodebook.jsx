import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import '../styles/Home.css'

export default function ApplyCodebook() {
  const navigate = useNavigate()
  const [apiKey, setApiKey] = useState('')
  const [methodology, setMethodology] = useState('')
  const [database, setDatabase] = useState('original')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!apiKey.trim()) {
      setError('API key is required')
      return
    }

    try {
      setLoading(true)
      setError(null)
      setResult(null)

      const formData = new FormData()
      formData.append('api_key', apiKey)
      formData.append('database', database)
      formData.append('methodology', methodology)

      const response = await fetch('/api/apply-codebook/', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleViewCoding = () => {
    navigate('/coding-view')
  }

  return (
    <>
      <Navbar />
      <div className="home-container">
        <div className="form-wrapper">
          <h1>Apply Codebook</h1>
          
          <div style={{ marginBottom: '30px', textAlign: 'center' }}>
            <button 
              onClick={handleViewCoding}
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
              View Coding Results
            </button>
          </div>

        <form onSubmit={handleSubmit} className="filter-form">
          <div className="form-group">
            <label htmlFor="apiKey">OpenRouter API Key</label>
            <input
              type="password"
              id="apiKey"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your OpenRouter API key..."
              className="filter-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="database">Data Source</label>
            <select
              id="database"
              value={database}
              onChange={(e) => setDatabase(e.target.value)}
              className="filter-input"
            >
              <option value="original">Original Data</option>
              <option value="filtered">Filtered Data</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="methodology">Methodology (Optional)</label>
            <textarea
              id="methodology"
              value={methodology}
              onChange={(e) => setMethodology(e.target.value)}
              placeholder="Enter your coding methodology or leave blank..."
              className="filter-input"
              rows="4"
            />
          </div>

          <button type="submit" disabled={loading} className="filter-submit-btn">
            {loading ? 'Applying...' : 'Apply Codebook'}
          </button>
        </form>

        {(error || (result && result.error)) && (
          <p className="filter-message">
            {error || result.error}
          </p>
        )}
        {result && result.classification_report && (
          <div className="result">
            <h2>Classification Report</h2>
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>{result.classification_report}</pre>
          </div>
        )}
        </div>
      </div>
    </>
  )
}
