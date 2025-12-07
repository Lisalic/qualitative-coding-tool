import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import { useState } from 'react'
import '../styles/Home.css'

export default function Filter() {
  const navigate = useNavigate()
  const [filterPrompt, setFilterPrompt] = useState('')
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

    setLoading(true)
    setMessage('')

    try {
      setMessage(`Filter applied: ${filterPrompt}`)
      setFilterPrompt('')
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
              <label htmlFor="filter-prompt">Filter Prompt</label>
              <input
                id="filter-prompt"
                type="text"
                placeholder="Enter your filter prompt..."
                value={filterPrompt}
                onChange={(e) => setFilterPrompt(e.target.value)}
                disabled={loading}
                className="filter-input"
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