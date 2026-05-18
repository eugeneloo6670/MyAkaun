import axios from "axios"

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
})

// Entries
export const getEntries = (params = {}) => api.get("/api/entries/", { params })
export const createEntry = (data) => api.post("/api/entries/", data)
export const deleteEntry = (id, deleted_by = "User") =>
  api.delete(`/api/entries/${id}`, { params: { deleted_by } })

// Soft-void an entry (preferred over delete). Pass { voided_by, reason? }.
export const voidEntry = (id, payload) =>
  api.post(`/api/entries/${id}/void`, payload)
export const getAuditLog = (params = {}) => api.get("/api/entries/audit-log/all", { params })
export const getSupplierMemory = () => api.get("/api/entries/supplier-memory/all")

// Periods
export const getPeriods = () => api.get("/api/periods/")
export const getCurrentPeriod = () => api.get("/api/periods/current")
export const getPeriodStatus = (month) => api.get(`/api/periods/${month}/status`)
export const setPeriodLock = (data) => api.post("/api/periods/lock", data)

// Reports
export const getMonthEnd = (month) => api.get(`/api/reports/month-end/${month}`)
export const getCreditors = () => api.get("/api/reports/creditors")
export const getAgedPayables = () => api.get("/api/reports/aged-payables")

export default api
