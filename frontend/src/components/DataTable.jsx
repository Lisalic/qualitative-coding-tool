import { useEffect, useState } from 'react'
import '../styles/DataTable.css'

export default function DataTable() {
  const [dbEntries, setDbEntries] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchEntries = async () => {
    try {
      setError('')
      setLoading(true)
      
      const response = await fetch(`/api/database-entries/?limit=10&database=original`)
      
      if (!response.ok) {
        const text = await response.text()
        throw new Error(`Failed to fetch database entries: ${response.status}`)
      }

      const text = await response.text()
      
      if (!text) {
        throw new Error('Empty response from server')
      }
      
      const data = JSON.parse(text)
      setDbEntries(data)
    } catch (err) {
      setError(`Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchEntries()
  }, [])

  return (
    <div className="data-table-container">
      <div className="table-header">
        <h2>Database Contents</h2>
      </div>

      {error && <p className="error-message">{error}</p>}

      {dbEntries && (
        <>
          <p className="stats">
            Total: {dbEntries.total_submissions} submissions, {dbEntries.total_comments} comments
          </p>

          {dbEntries.message && <p className="info-message">{dbEntries.message}</p>}

          {dbEntries.submissions.length > 0 && (
            <div className="table-section">
              <h3>Sample Submissions (10)</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Subreddit</th>
                      <th>Title</th>
                      <th>Author</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dbEntries.submissions.map((sub) => (
                      <tr key={sub.id}>
                        <td>{sub.id}</td>
                        <td>{sub.subreddit}</td>
                        <td className="truncate">{sub.title}</td>
                        <td>{sub.author}</td>
                        <td>{sub.score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {dbEntries.comments.length > 0 && (
            <div className="table-section">
              <h3>Sample Comments (10)</h3>
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Subreddit</th>
                      <th>Body</th>
                      <th>Author</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dbEntries.comments.map((comment) => (
                      <tr key={comment.id}>
                        <td>{comment.id}</td>
                        <td>{comment.subreddit}</td>
                        <td className="truncate">{comment.body}</td>
                        <td>{comment.author}</td>
                        <td>{comment.score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {dbEntries.submissions.length === 0 && dbEntries.comments.length === 0 && (
            <p className="no-data">No data available. Please upload a file first.</p>
          )}
        </>
      )}

    </div>
  )
}
