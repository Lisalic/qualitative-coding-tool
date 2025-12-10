import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import Navbar from '../components/Navbar'
import '../styles/Data.css'

export default function ViewCodebook() {
  const navigate = useNavigate()
  const [codebooks, setCodebooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const handleBack = () => {
    navigate('/')
  }

  const fetchCodebooks = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch('/api/codebook')
      if (!response.ok) {
        throw new Error('Failed to fetch codebook')
      }
      const data = await response.json()
      if (data.codebook) {
        setCodebooks([{ content: data.codebook }])
      } else {
        setCodebooks([])
      }
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
      <Navbar onBack={handleBack} />
      <div className="data-container">
        <div style={{
          border: '1px solid #ffffff',
          borderRadius: '8px',
          padding: '20px',
          backgroundColor: '#000000'
        }}>
          <h1 style={{ textAlign: 'center', color: '#ffffff' }}>View Codebook</h1>

          {loading && <p>Loading codebooks...</p>}
          {error && <div style={{color: '#ff6666', padding: '10px', border: '1px solid #ff6666', borderRadius: '4px', marginBottom: '20px'}}>{error}</div>}
          
          {codebooks.length > 0 && (
            <div>
              <div style={{
                backgroundColor: '#000000',
                border: '1px solid #ffffff',
                borderRadius: '4px',
                padding: '20px',
                color: '#ffffff'
              }}>
                <ReactMarkdown
                  components={{
                    h3: ({ children }) => <h3 style={{ color: '#ffffff', marginTop: '20px' }}>{children}</h3>,
                    h4: ({ children }) => <h4 style={{ color: '#ffffff', marginTop: '15px' }}>{children}</h4>,
                    ul: ({ children }) => <ul style={{ color: '#ffffff' }}>{children}</ul>,
                    li: ({ children }) => <li style={{ color: '#ffffff' }}>{children}</li>,
                    strong: ({ children }) => <strong style={{ color: '#ffffff' }}>{children}</strong>,
                    p: ({ children }) => <p style={{ color: '#ffffff' }}>{children}</p>,
                  }}
                >
                  {codebooks[0].content}
                </ReactMarkdown>
              </div>
            </div>
          )}

          {codebooks.length === 0 && !loading && !error && (
            <p>No codebook found. Generate a codebook first.</p>
          )}
        </div>
      </div>
    </>
  )
}
