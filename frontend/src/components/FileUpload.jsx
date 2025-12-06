import { useState } from 'react'
import '../styles/FileUpload.css'

export default function FileUpload({ onUploadSuccess, onError }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile && selectedFile.name.endsWith('.zst')) {
      setFile(selectedFile)
      onError('')
    } else {
      onError('Please select a .zst file')
      setFile(null)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!file) {
      onError('Please select a file')
      return
    }

    setLoading(true)
    setMessage('')
    onError('')

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/upload-zst/', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const text = await response.text()
        let errorMsg = 'Upload failed'
        try {
          const errorData = JSON.parse(text)
          errorMsg = errorData.detail || errorMsg
        } catch (e) {
          errorMsg = text || errorMsg
        }
        throw new Error(errorMsg)
      }

      const text = await response.text()
      if (!text) {
        throw new Error('Empty response from server')
      }
      const data = JSON.parse(text)
      setMessage('✓ reddit_data.db updated')
      setFile(null)
      setLoading(false)
      
      onUploadSuccess(data)
    } catch (err) {
      onError(`Error: ${err.message}`)
      setLoading(false)
    }
  }

  return (
    <div className="file-upload">
      <h2>Upload Reddit Data</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="zst-file">Upload .zst File</label>
          <input
            id="zst-file"
            type="file"
            accept=".zst"
            onChange={handleFileChange}
            disabled={loading}
          />
          {file && <p className="file-name">Selected: {file.name}</p>}
        </div>

        <button type="submit" disabled={loading}>
          {loading ? 'Processing...' : 'Upload'}
        </button>
      </form>

      {message && <p className="success-message">{message}</p>}
    </div>
  )
}
