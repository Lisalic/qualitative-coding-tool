import { useState } from 'react'
import '../styles/FileUpload.css'

export default function FileUpload({ onUploadSuccess, onError }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [subredditInput, setSubredditInput] = useState('')
  const [subredditTags, setSubredditTags] = useState([])

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

  const handleAddSubreddit = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      const value = subredditInput.trim().replace(/,\s*$/, '')
      if (value && !subredditTags.includes(value.toLowerCase())) {
        setSubredditTags([...subredditTags, value.toLowerCase()])
        setSubredditInput('')
      }
    }
  }

  const handleAddSubredditClick = () => {
    const value = subredditInput.trim()
    if (value && !subredditTags.includes(value.toLowerCase())) {
      setSubredditTags([...subredditTags, value.toLowerCase()])
      setSubredditInput('')
    }
  }

  const handleRemoveSubreddit = (index) => {
    setSubredditTags(subredditTags.filter((_, i) => i !== index))
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
      
      if (subredditTags.length > 0) {
        formData.append('subreddits', JSON.stringify(subredditTags))
      }

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
      setSubredditTags([])
      setSubredditInput('')
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

        <div className="form-group">
          <label htmlFor="subreddits">Filter by Subreddits</label>
          <div className="subreddit-input-wrapper">
            <div className="subreddit-input-group">
              <input
                id="subreddits"
                type="text"
                placeholder="Enter subreddit name..."
                value={subredditInput}
                onChange={(e) => setSubredditInput(e.target.value)}
                onKeyDown={handleAddSubreddit}
                disabled={loading}
              />
              <button
                type="button"
                className="add-btn"
                onClick={handleAddSubredditClick}
                disabled={loading || !subredditInput.trim()}
              >
                Add
              </button>
            </div>
            <div className="subreddit-tags">
              {subredditTags.map((subreddit, index) => (
                <div key={index} className="tag">
                  <span>{subreddit}</span>
                  <button
                    type="button"
                    className="tag-remove"
                    onClick={() => handleRemoveSubreddit(index)}
                    disabled={loading}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        <button type="submit" disabled={loading}>
          {loading ? 'Processing...' : 'Upload'}
        </button>
      </form>

      {message && <p className="success-message">{message}</p>}
    </div>
  )
}
