import '../styles/ErrorDisplay.css'

export default function ErrorDisplay({ message, onDismiss }) {
  if (!message) return null

  return (
    <div className="error-display">
      <p className="error-message">{message}</p>
      {onDismiss && (
        <button onClick={onDismiss} className="dismiss-btn">×</button>
      )}
    </div>
  )
}
