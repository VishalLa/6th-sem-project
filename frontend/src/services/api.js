import axios from 'axios'

const API = axios.create({
  baseURL: 'http://127.0.0.1:8000/',
  timeout: 180_000
})

// ── Auth token injection ──────────────────────────────────────────────────────
API.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// ── Global 401 / 403 handler ─────────────────────────────────────────────────
API.interceptors.response.use(
  res => res,
  async err => {
    const status = err.response?.status
    if (status === 401 || status === 403) {
      localStorage.removeItem('token')
      try {
        const { useAuthStore } = await import('@/stores/auth')
        const auth = useAuthStore()
        auth.logout()
      } catch (_) {}
      if (!window.location.hash.includes('/auth')) {
        window.location.hash = '#/auth'
      }
    }
    return Promise.reject(err)
  }
)

// ── Auth ─────────────────────────────────────────────────────────────────────
export const loginUser = (email, password) => {
  const fd = new URLSearchParams()
  fd.append('username', email)
  fd.append('password', password)
  return API.post('/auth/login', fd, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
}

export const registerUser = (payload) => API.post('/auth/register', payload)

export const getMyProfile = () => API.get('/users/me')

// ── Detection (original flow preserved) ──────────────────────────────────────
export const uploadFiles = (files) => {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  return API.post('/upload/detect', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}

// Full pipeline — stores to DB + FAISS, returns batch_id + stats
export const uploadFullPipeline = (file, opts = {}) => {
  const fd = new FormData()
  fd.append('file', file)
  const params = new URLSearchParams({
    save_transactions:  opts.saveTransactions  ?? true,
    save_summary:       opts.saveSummary       ?? true,
    embed_transactions: opts.embedTransactions ?? true,
    embed_results:      opts.embedResults      ?? true,
  })
  return API.post(`/upload/full-pipeline?${params}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}

// ── Transactions & Fraud rings (cross-batch) ──────────────────────────────────
export const getMyTransactions = (limit = 200, offset = 0) =>
  API.get('/my-transactions', { params: { limit, offset } })

export const getMyFraudRings = (limit = 100, offset = 0) =>
  API.get('/my-fraud-rings', { params: { limit, offset } })

// ── Batch Management ──────────────────────────────────────────────────────────
/** List all upload batches for the current user (newest first). */
export const getMyBatches = (limit = 50, offset = 0) =>
  API.get('/my-batches', { params: { limit, offset } })

/** Transactions scoped to a specific upload batch. */
export const getBatchTransactions = (batchId, limit = 200, offset = 0) =>
  API.get(`/batch/${batchId}/transactions`, { params: { limit, offset } })

/** Fraud rings scoped to a specific upload batch. */
export const getBatchFraudRings = (batchId, limit = 100, offset = 0) =>
  API.get(`/batch/${batchId}/fraud-rings`, { params: { limit, offset } })

/** Full JSON fraud detection report for a specific batch. */
export const getBatchReport = (batchId) =>
  API.get(`/batch/${batchId}/report`)

/** Download the JSON report file for a batch (blob). */
export const downloadBatchJson = (batchId) =>
  API.get(`/batch/${batchId}/download/json`, { responseType: 'blob' })

/** Download a CSV summary for a batch (blob). */
export const downloadBatchCsv = (batchId) =>
  API.get(`/batch/${batchId}/download/csv`, { responseType: 'blob' })

/** Permanently delete a batch and all its associated data. */
export const deleteBatch = (batchId) =>
  API.delete(`/batch/${batchId}`)

/** Delete the FAISS vector index for a specific batch. */
export const deleteIndex = (batchId) =>
  API.delete(`/index/${batchId}`)

// ── Reports (legacy file-based) ────────────────────────────────────────────────
export const fetchFileList    = () => API.get('/my-reports')
export const downloadFile     = (fileName) => API.get(`/download/json/${fileName}`, { responseType: 'blob' })
export const downloadCSV      = (fileName) => API.get(`/download/csv/${fileName}`,  { responseType: 'blob' })

// ── Chatbot ───────────────────────────────────────────────────────────────────
export const chatbotQuery = (query, sessionId = 'default') =>
  API.post('/chatbot/query', { query, session_id: sessionId, include_followup: true })

export const chatbotDatasetInfo = () => API.get('/chatbot/dataset/info')

export const chatbotResetSession = (sessionId = 'default') =>
  API.post(`/chatbot/session/${sessionId}/reset`)

export const getChatbotSession = (sessionId = 'default') =>
  API.get(`/chatbot/session/${sessionId}`)

export const clearChatbotCache = () =>
  API.delete('/chatbot/cache')

export const buildVectorDB = (forceRebuild = false) =>
  API.post('/chatbot/vector-db/build', { force_rebuild: forceRebuild })

export default API
