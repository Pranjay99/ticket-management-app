import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1', timeout: 30000 })

api.interceptors.response.use(
  r => r.data,
  err => Promise.reject(err?.response?.data?.detail ?? err.message ?? 'Unknown error'),
)

const p = (obj) => {
  const out = {}
  Object.entries(obj).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') out[k] = v })
  return out
}

export const getSummary       = (f = {}) => api.get('/insights/summary',               { params: p(f) })
export const getTrends        = (f = {}) => api.get('/insights/trends',                { params: p(f) })
export const getCategories    = (f = {}) => api.get('/insights/categories',            { params: p(f) })
export const getSentimentDist = (f = {}) => api.get('/insights/sentiment-distribution', { params: p(f) })
export const getTopProducts   = (f = {}) => api.get('/insights/products',              { params: p({ limit: 8, ...f }) })
export const getRevenueRisk   = (f = {}) => api.get('/insights/revenue-risk',          { params: p(f) })
export const getCountries     = (f = {}) => api.get('/insights/countries',             { params: p({ limit: 8, ...f }) })
export const getTopIssues     = (f = {}) => api.get('/insights/top-issues',            { params: p({ limit: 8, ...f }) })
export const getVelocity      = (f = {}) => api.get('/insights/velocity',              { params: p(f) })

export const listTickets    = (params) => api.get('/tickets', { params })
export const resolveTicket  = (id)     => api.patch(`/tickets/${id}/resolve`)
export const escalateTicket = (id)     => api.patch(`/tickets/${id}/escalate`)
export const suggestReply   = (data)   => api.post('/suggest', data)
export const searchTickets  = (data)   => api.post('/tickets/search', data)

export const uploadCSV          = (formData) => api.post('/tickets/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const getTaskStatus      = (taskId)   => api.get(`/tickets/task/${taskId}`)
export const getSampleCSVUrl    = ()         => '/api/v1/tickets/download/sample'
