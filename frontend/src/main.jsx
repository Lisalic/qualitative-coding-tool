import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// Suppress the browser's history-suggestion popup on plain text/search inputs
// (login's email/password fields are untouched so password managers still work).
document.addEventListener('focusin', (e) => {
  const el = e.target
  if (
    el instanceof HTMLInputElement &&
    (el.type === 'text' || el.type === 'search') &&
    !el.hasAttribute('autocomplete')
  ) {
    el.setAttribute('autocomplete', 'off')
  }
  if (el instanceof HTMLTextAreaElement && !el.hasAttribute('autocomplete')) {
    el.setAttribute('autocomplete', 'off')
  }
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
