import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'
import '../styles/Data.css'

export default function ViewCodebook() {
  const [codebooks, setCodebooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchCodebooks = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch(
        `http://localhost:8000/api/database-entries/?limit=50&database=codebook`
      )
      if (!response.ok) {
        throw new Error('Failed to fetch codebooks')
      }
      const data = await response.json()
      setCodebooks(data.submissions || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCodebooks()
  }, [])

  return (
    <>
      <Navbar />
      <div className="data-container">
        <h1>View Codebook</h1>
        <p>Review and manage your coding schemes</p>

        {loading && <p>Loading codebooks...</p>}
        {error && <div style={{color: '#ff6666', padding: '10px', border: '1px solid #ff6666', borderRadius: '4px', marginBottom: '20px'}}>{error}</div>}
        
        {codebooks.length > 0 && (
          <div>
            <h2>Available Codebooks</h2>
            <div style={{display: 'grid', gap: '20px'}}>
              {codebooks.map((codebook, index) => (
                <div key={index} style={{
                  backgroundColor: '#000000',
                  border: '1px solid #ffffff',
                  borderRadius: '4px',
                  padding: '20px',
                  color: '#ffffff'
                }}>
                  <h3>{codebook.name || `Codebook ${index + 1}`}</h3>
                  <p>{codebook.description || 'No description available'}</p>
                  {codebook.categories && (
                    <ul style={{color: '#cccccc'}}>
                      {JSON.parse(codebook.categories || '[]').map((category, idx) => (
                        <li key={idx}>{category.name}: {category.codes.join(', ')}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {codebooks.length === 0 && !loading && !error && (
          <p>No codebooks found. Generate a codebook first.</p>
        )}
      </div>
    </>
  )
}
