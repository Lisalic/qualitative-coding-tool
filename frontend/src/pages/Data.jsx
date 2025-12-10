import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import DataTable from '../components/DataTable'
import '../styles/Data.css'

export default function Data() {
  const navigate = useNavigate()

  const handleBack = () => {
    navigate('/')
  }

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
      <div className="data-container">
        <DataTable title="View Data" />
      </div>
    </>
  )
}
