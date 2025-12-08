import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'
import '../styles/Data.css'

export default function FilteredData() {
  const [submissions, setSubmissions] = useState([])
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [limit, setLimit] = useState(5)

  useEffect(() => {
    fetchFilteredData()
  }, [limit])

  const fetchFilteredData = async () => {
    try {
      setLoading(true)
      const response = await fetch(
        `http://localhost:8000/api/database-entries/?limit=${limit}&database=filtered`
      )
      if (!response.ok) {
        throw new Error('Failed to fetch filtered data')
      }
      const data = await response.json()
      setSubmissions(data.submissions || [])
      setComments(data.comments || [])
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Navbar />
      <div className="data-container">
        <h1>Filtered Data</h1>

        <div className="controls">
          <label>
            Results per table:
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(Math.max(1, parseInt(e.target.value) || 5))}
              min="1"
              max="100"
            />
          </label>
          <button onClick={fetchFilteredData} className="refresh-btn">
            Refresh
          </button>
        </div>

        {error && <div className="error">{error}</div>}
        {loading && <div className="loading">Loading filtered data...</div>}

        {!loading && !error && (
          <>
            <div className="data-section">
              <h2>Filtered Submissions</h2>
              {submissions.length > 0 ? (
                <div className="data-grid">
                  {submissions.map((item) => (
                    <div key={item.id} className="data-item">
                      <h3>{item.title}</h3>
                      <p className="meta">by {item.author}</p>
                      <p>{item.selftext?.substring(0, 200)}...</p>
                      <p className="score">Score: {item.score}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p>No filtered submissions found.</p>
              )}
            </div>

            <div className="data-section">
              <h2>Filtered Comments</h2>
              {comments.length > 0 ? (
                <div className="data-grid">
                  {comments.map((item) => (
                    <div key={item.id} className="data-item">
                      <p className="meta">by {item.author}</p>
                      <p>{item.body?.substring(0, 200)}...</p>
                      <p className="score">Score: {item.score}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p>No filtered comments found.</p>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
