import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import ActionForm from '../components/ActionForm'
import '../styles/Home.css'

export default function GenerateCodebook() {
  const navigate = useNavigate()
  const [database, setDatabase] = useState('original')
  const [apiKey, setApiKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleViewCodebook = () => {
    navigate('/codebook-view')
  }

  const handleSubmit = async (formData) => {
    try {
      setLoading(true)
      setError(null)
      setResult(null)

      const requestData = new FormData()
      requestData.append('database', formData.database)
      requestData.append('api_key', formData.apiKey)

      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 60000)

      const response = await fetch('/api/generate-codebook/', {
        method: 'POST',
        body: requestData,
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

  const fields = [
    {
      id: 'database',
      label: 'Database',
      type: 'select',
      value: database,
      options: [
        { value: 'original', label: 'Reddit Data' },
        { value: 'filtered', label: 'Filtered Data' }
      ]
    },
    {
      id: 'apiKey',
      label: 'OpenRouter API Key',
      type: 'password',
      value: apiKey,
      placeholder: 'Enter your OpenRouter API key',
      required: true
    }
  ]

  return (
    <>
      <Navbar />
      <ActionForm
        title="Generate Codebook"
        viewButton={{
          text: 'View Codebook',
          onClick: handleViewCodebook
        }}
        fields={fields}
        submitButton={{
          text: 'Generate Codebook',
          loadingText: 'Generating...',
          disabled: loading
        }}
        onSubmit={handleSubmit}
        error={error}
        result={result}
        resultTitle="Generated Codebook"
      />
    </>
  )
}
