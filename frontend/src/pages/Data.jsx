import { useNavigate } from 'react-router-dom'
import DataTable from '../components/DataTable'
import '../styles/Data.css'

export default function Data() {
  const navigate = useNavigate()

  return (
    <div className="data-container">
      <div className="data-header">
        <button onClick={() => navigate('/')} className="back-btn">
          ← Back
        </button>
      </div>
      <DataTable />
    </div>
  )
}
