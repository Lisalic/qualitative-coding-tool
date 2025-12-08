import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'
import '../styles/Data.css'

export default function ViewCoding() {
  const [codings, setCodings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchCodings = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch(
        `http://localhost:8000/api/database-entries/?limit=50&database=coding`
      )
      if (!response.ok) {
        throw new Error('Failed to fetch codings')
      }
      const data = await response.json()
      setCodings(data.submissions || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCodings()
  }, [])

  return (
    <>
      <Navbar />
      <div className="data-container">
        <h1>View Coding</h1>
        <p>Review coded items with applied codes</p>

        {loading && <p>Loading codings...</p>}
        {error && <div style={{color: '#ff6666', padding: '10px', border: '1px solid #ff6666', borderRadius: '4px', marginBottom: '20px'}}>{error}</div>}
        
        {codings.length > 0 && (
          <div>
            <h2>Coded Items ({codings.length})</h2>
            <div style={{display: 'grid', gap: '20px'}}>
              {codings.map((coding, index) => (
                <div key={index} style={{
                  backgroundColor: '#000000',
                  border: '1px solid #ffffff',
                  borderRadius: '4px',
                  padding: '20px',
                  color: '#ffffff'
                }}>
                  <h3>Item {index + 1}</h3>
                  <p><strong>Text:</strong> {coding.text || 'No text available'}</p>
                  <p><strong>Codes:</strong> {coding.codes || 'No codes applied'}</p>
                  <p><strong>Author:</strong> {coding.author || 'Unknown'}</p>
                  {coding.timestamp && <p><strong>Timestamp:</strong> {coding.timestamp}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {codings.length === 0 && !loading && !error && (
          <p>No coded items found. Apply a codebook first.</p>
        )}
      </div>
    </>
  )
}
