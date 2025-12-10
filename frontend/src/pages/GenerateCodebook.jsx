import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'
import '../styles/Home.css'

export default function GenerateCodebook() {
  const [database, setDatabase] = useState('original')
  const [apiKey, setApiKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!apiKey.trim()) {
      setError('OpenRouter API key is required')
      return
    }

    try {
      setLoading(true)
      setError(null)
      setResult(null)

      const formData = new FormData()
      formData.append('database', database)
      formData.append('api_key', apiKey)

      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 60000)

      const response = await fetch('/api/filter-data/', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      if (data.error) {
        setError(data.error)
      } else {
        setResult(data.codebook)
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Request timed out. Please try again.')
      } else {
        setError(err.message)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Navbar />
      <div className="home-container">
        <div className="form-wrapper">
          <h1>Generate Codebook</h1>

          <form onSubmit={handleSubmit} className="filter-form">
            <div className="form-group">
              <label htmlFor="database">Database</label>
              <select
                id="database"
                value={database}
                onChange={(e) => setDatabase(e.target.value)}
                className="filter-input"
              >
                <option value="original">Reddit Data</option>
                <option value="filtered">Filtered Data</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="apiKey">OpenRouter API Key</label>
              <input
                type="password"
                id="apiKey"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your OpenRouter API key"
                className="filter-input"
                required
              />
            </div>

            <button type="submit" disabled={loading} className="filter-submit-btn">
              {loading ? 'Generating...' : 'Generate Codebook'}
            </button>
        </form>

        {error && (
          <p className="filter-message">
            {error}
          </p>
        )}
        {result && (
          <div className="result">
            <h2>Generated Codebook</h2>
            <pre>{result}</pre>
          </div>
        )}
        </div>
      </div>
    </>
  )
}
