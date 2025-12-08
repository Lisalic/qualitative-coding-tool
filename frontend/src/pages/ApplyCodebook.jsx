import { useState } from 'react'
import Navbar from '../components/Navbar'
import '../styles/Home.css'

export default function ApplyCodebook() {
  const [apiKey, setApiKey] = useState('')
  const [codebook, setCodebook] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!apiKey.trim()) {
      setError('API key is required')
      return
    }

    if (!codebook.trim()) {
      setError('Codebook is required')
      return
    }

    try {
      setLoading(true)
      setError(null)
      setResult(null)

      const formData = new FormData()
      formData.append('api_key', apiKey)
      formData.append('prompt', codebook)

      const response = await fetch('http://localhost:8000/api/filter-data/', {
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

  return (
    <>
      <Navbar />
      <div className="home-container">
        <div className="form-wrapper">
          <h1>Apply Codebook</h1>

        <form onSubmit={handleSubmit} className="filter-form">
          <div className="form-group">
            <label htmlFor="apiKey">Google Gemini API Key</label>
            <input
              type="password"
              id="apiKey"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your Google Gemini API key..."
              className="filter-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="codebook">Codebook</label>
            <textarea
              id="codebook"
              value={codebook}
              onChange={(e) => setCodebook(e.target.value)}
              placeholder="Paste your codebook or coding instructions..."
              className="filter-input"
              rows="8"
            />
          </div>

          <button type="submit" disabled={loading} className="filter-submit-btn">
            {loading ? 'Applying...' : 'Apply Codebook'}
          </button>
        </form>

        {(error || (result && result.message)) && (
          <p className="filter-message">
            {error || result.message}
          </p>
        )}
        {result && !result.message && (
          <div className="result">
            <h2>Coding Results</h2>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </div>
        )}
        </div>
      </div>
    </>
  )
}
