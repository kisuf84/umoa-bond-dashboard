import { useState, useEffect } from 'react'
import axios from 'axios'
import './AdminUpload.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

function AdminUpload() {
  // PDF Upload State
  const [pdfFile, setPdfFile] = useState(null)
  const [pdfUploading, setPdfUploading] = useState(false)
  const [pdfMessage, setPdfMessage] = useState(null)
  const [pdfNextDue, setPdfNextDue] = useState('')

  // Excel Upload State
  const [excelFile, setExcelFile] = useState(null)
  const [excelUploading, setExcelUploading] = useState(false)
  const [excelMessage, setExcelMessage] = useState(null)
  const [excelNextDue, setExcelNextDue] = useState('')

  // Upload History State
  const [uploadHistory, setUploadHistory] = useState({ pdf: [], excel: [] })

  useEffect(() => {
    loadUploadHistory()
  }, [])

  const loadUploadHistory = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/upload-history`)
      setUploadHistory(response.data)
    } catch (err) {
      console.error('Failed to load upload history:', err)
    }
  }

  const handlePdfSubmit = async (e) => {
    e.preventDefault()
    if (!pdfFile) {
      setPdfMessage({ type: 'error', text: 'Please select a PDF file' })
      return
    }

    const formData = new FormData()
    formData.append('file', pdfFile)

    setPdfUploading(true)
    setPdfMessage(null)

    try {
      const response = await axios.post(`${API_URL}/api/upload-pdf`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setPdfMessage({ type: 'success', text: `Uploaded successfully: ${response.data.total_records || 0} records` })
      setPdfFile(null)
      document.getElementById('pdf-file').value = ''
      loadUploadHistory()
    } catch (err) {
      setPdfMessage({ type: 'error', text: err.response?.data?.error || 'Upload failed' })
    } finally {
      setPdfUploading(false)
    }
  }

  const handleExcelSubmit = async (e) => {
    e.preventDefault()
    if (!excelFile) {
      setExcelMessage({ type: 'error', text: 'Please select an Excel file' })
      return
    }

    const formData = new FormData()
    formData.append('file', excelFile)

    setExcelUploading(true)
    setExcelMessage(null)

    try {
      const response = await axios.post(`${API_URL}/api/upload-excel`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      const msg = `Uploaded successfully: ${response.data.countries_parsed} countries, ${response.data.total_rows} data points`
      setExcelMessage({ type: 'success', text: msg })
      setExcelFile(null)
      document.getElementById('excel-file').value = ''
      loadUploadHistory()
    } catch (err) {
      const errMsg = err.response?.data?.error || 'Upload failed'
      const warnings = err.response?.data?.warnings?.join(', ') || ''
      setExcelMessage({ type: 'error', text: warnings ? `${errMsg}: ${warnings}` : errMsg })
    } finally {
      setExcelUploading(false)
    }
  }

  // Format date as DD/MM/YYYY HH:MM (French format)
  const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    const day = String(date.getDate()).padStart(2, '0')
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const year = date.getFullYear()
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${day}/${month}/${year} ${hours}:${minutes}`
  }

  return (
    <div className="admin-container">
      <div className="admin-header">
        <h1>📁 Admin Upload Portal</h1>
        <p>Upload monthly bond data (PDF) and weekly yield curves (Excel)</p>
      </div>

      <div className="upload-sections">
        {/* PDF Upload Section */}
        <div className="upload-section">
          <div className="section-header">
            <h2>📄 Monthly PDF Upload</h2>
            <span className="badge badge-monthly">Monthly</span>
          </div>
          <p className="section-desc">Upload UMOA Titres monthly bond listing PDF</p>

          <form onSubmit={handlePdfSubmit} className="upload-form">
            <div className="file-input-wrapper">
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => { setPdfFile(e.target.files[0]); setPdfMessage(null) }}
                id="pdf-file"
              />
              <label htmlFor="pdf-file" className="file-label">
                {pdfFile ? pdfFile.name : 'Choose PDF file...'}
              </label>
            </div>

            <div className="form-row">
              <label>Next upload due:</label>
              <input
                type="date"
                value={pdfNextDue}
                onChange={(e) => setPdfNextDue(e.target.value)}
                className="date-input"
              />
            </div>

            <button type="submit" disabled={pdfUploading || !pdfFile} className="upload-btn">
              {pdfUploading ? 'Uploading...' : 'Upload PDF'}
            </button>
          </form>

          {pdfMessage && (
            <div className={`message ${pdfMessage.type}`}>
              {pdfMessage.text}
            </div>
          )}

          <div className="history-section">
            <h3>Upload History</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Date</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {uploadHistory.pdf?.length > 0 ? (
                    uploadHistory.pdf.slice(0, 5).map((item, idx) => (
                      <tr key={idx}>
                        <td className="filename">{item.filename}</td>
                        <td>{formatDate(item.upload_date)}</td>
                        <td>
                          <span className={`status-badge status-${item.status}`}>
                            {item.status}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="3" className="no-data">No uploads yet</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Excel Upload Section */}
        <div className="upload-section">
          <div className="section-header">
            <h2>📊 Weekly Excel Upload</h2>
            <span className="badge badge-weekly">Weekly</span>
          </div>
          <p className="section-desc">Upload yield curve data for all 8 UMOA countries</p>

          <form onSubmit={handleExcelSubmit} className="upload-form">
            <div className="file-input-wrapper">
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => { setExcelFile(e.target.files[0]); setExcelMessage(null) }}
                id="excel-file"
              />
              <label htmlFor="excel-file" className="file-label">
                {excelFile ? excelFile.name : 'Choose Excel file...'}
              </label>
            </div>

            <div className="form-row">
              <label>Next upload due:</label>
              <input
                type="date"
                value={excelNextDue}
                onChange={(e) => setExcelNextDue(e.target.value)}
                className="date-input"
              />
            </div>

            <button type="submit" disabled={excelUploading || !excelFile} className="upload-btn">
              {excelUploading ? 'Uploading...' : 'Upload Excel'}
            </button>
          </form>

          {excelMessage && (
            <div className={`message ${excelMessage.type}`}>
              {excelMessage.text}
            </div>
          )}

          <div className="history-section">
            <h3>Upload History</h3>
            <div className="history-table-wrapper">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Date</th>
                    <th>Records</th>
                  </tr>
                </thead>
                <tbody>
                  {uploadHistory.excel?.length > 0 ? (
                    uploadHistory.excel.slice(0, 5).map((item, idx) => (
                      <tr key={idx}>
                        <td className="filename">{item.filename}</td>
                        <td>{formatDate(item.upload_date)}</td>
                        <td>{item.records}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan="3" className="no-data">No uploads yet</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AdminUpload
