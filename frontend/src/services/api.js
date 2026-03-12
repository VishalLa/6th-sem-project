import axios from 'axios'

const API = axios.create({
  baseURL: 'http://127.0.0.1:8000/',
  timeout: 180_000  // detection can take time on large CSVs
})

/**
 * POST /input/files
 * Sends multipart CSV files.
 *
 * Backend returns:
 * {
 *   "<filename.csv>": {
 *     report: {
 *       suspicious_accounts: [...],
 *       fraud_rings:         [...],   // {ring_id, pattern_type, member_accounts[], risk_score}
 *       summary: { total_accounts_analyzed, suspicious_accounts_flagged,
 *                  fraud_rings_detected, processing_time_seconds }
 *     },
 *     summary: [   // ← summary_table rows as records
 *       {
 *         "Ring ID", "Pattern Type", "Member Count", "Risk Score",
 *         "Member Account IDs", "Avg Member Score", "Max Member Score",
 *         "Structural Complexity", "Internal Edge Count",
 *         "Ring Density", "Risk Category"
 *       }, ...
 *     ],
 *     saved_to: "output/filename_analysis.json"
 *   }
 * }
 */
export const uploadFiles = (files) => {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  return API.post('/input/files', fd, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * GET /show/output/files
 * Returns: { files: [{ name, download_url }] }
 */
export const fetchFileList = () => API.get('/show/output/files')

/**
 * GET /download/{file_name}
 * NOTE: backend appends ".json" itself, so pass without extension.
 * Returns: FileResponse (application/json blob)
 */
export const downloadFile = (fileName) =>
  API.get(`/download/${fileName}`, { responseType: 'blob' })

export default API
