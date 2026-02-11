import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import AdminUpload from './components/AdminUpload'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/admin-upload-secret-2026" element={<AdminUpload />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
