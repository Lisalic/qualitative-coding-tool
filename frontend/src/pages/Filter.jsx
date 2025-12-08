import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { useState } from 'react'
import '../styles/Home.css'

export default function Filter() {
  const navigate = useNavigate()
  const [filterPrompt, setFilterPrompt] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const handleBack = () => {
    navigate('/')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!filterPrompt.trim()) {
      setMessage('Please enter a filter prompt')
      return
    }

    if (!apiKey.trim()) {
      setMessage('Please enter a Google Gemini API key')
      return
    }

    setLoading(true)
    setMessage('')

    try {
      const formData = new FormData()
      formData.append('api_key', apiKey)
      formData.append('prompt', filterPrompt)

      const response = await fetch('/api/filter-data/', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const text = await response.text()
        let errorMsg = 'Filtering failed'
        try {
          const errorData = JSON.parse(text)
          errorMsg = errorData.detail || errorMsg
        } catch (e) {
          errorMsg = text || errorMsg
        }
        throw new Error(errorMsg)
      }

      const text = await response.text()
      const data = JSON.parse(text)

      setMessage(`✓ ${data.message}`)
      setFilterPrompt('')
      setApiKey('')
    } catch (err) {
      setMessage(`Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
      <div className="home-container">
        <div className="form-wrapper">
          <h1>Filter Data</h1>
          <form onSubmit={handleSubmit} className="filter-form">
            <div className="form-group">
              <label htmlFor="api-key">Google Gemini API Key</label>
              <input
                id="api-key"
                type="password"
                placeholder="Enter your Google Gemini API key..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                disabled={loading}
                className="filter-input"
              />
            </div>
            <div className="form-group">
              <label htmlFor="filter-prompt">Filter Prompt</label>
              <textarea
                id="filter-prompt"
                placeholder="Enter your filter prompt..."
                value={filterPrompt}
                onChange={(e) => setFilterPrompt(e.target.value)}
                disabled={loading}
                className="filter-input"
                rows="5"
              />
            </div>
            <button type="submit" disabled={loading} className="filter-submit-btn">
              {loading ? 'Processing...' : 'Filter'}
            </button>
            {message && <p className="filter-message">{message}</p>}
          </form>
        </div>
      </div>
    </>
  )
}