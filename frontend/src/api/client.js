import axios from "axios";

// All requests go through Vite's proxy to the FastAPI backend.
const http = axios.create({ baseURL: "/", timeout: 30000 });

// Surface backend error detail in a consistent shape for the UI.
http.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail;
    err.userMessage =
      typeof detail === "string"
        ? detail
        : detail?.message || err.message || "Beklenmeyen bir hata oluştu.";
    return Promise.reject(err);
  }
);

// Build a query string, dropping null/undefined/empty values.
function qs(params = {}) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === null || v === undefined || v === "") return;
    if (Array.isArray(v)) v.forEach((item) => sp.append(k, item));
    else sp.append(k, v);
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  // Import
  uploadCsv: (file, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    return http.post("/api/import/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: onProgress,
      timeout: 180000, // large files (50K+ rows) import+validate synchronously
    });
  },
  listBatches: () => http.get("/api/import/batches"),
  getBatch: (id) => http.get(`/api/import/batches/${id}`),
  deleteBatch: (id) => http.delete(`/api/import/batches/${id}`),

  // Records
  listRecords: (params) => http.get(`/api/records${qs(params)}`),
  getRecord: (id) => http.get(`/api/records/${id}`),
  getRecordErrors: (id) => http.get(`/api/records/${id}/errors`),
  getRecordAudit: (id) => http.get(`/api/records/${id}/audit-log`),
  updateRecord: (id, body) => http.put(`/api/records/${id}`, body),
  changeStatus: (id, action, reason) =>
    http.patch(`/api/records/${id}/status`, { action, reason }),
  batchAction: (ids, action, reason) =>
    http.post("/api/records/batch-action", { ids, action, reason }),

  // Reports
  summary: (params) => http.get(`/api/reports/summary${qs(params)}`),
  oeeTrend: (params) => http.get(`/api/reports/oee-trend${qs(params)}`),
  shiftComparison: (params) => http.get(`/api/reports/shift-comparison${qs(params)}`),
  stationRanking: (params) => http.get(`/api/reports/station-ranking${qs(params)}`),
  qualityDistribution: (params) =>
    http.get(`/api/reports/quality-distribution${qs(params)}`),
  lossAnalysis: (params) => http.get(`/api/reports/loss-analysis${qs(params)}`),

  // Validation
  validationSummary: (params) => http.get(`/api/validation/summary${qs(params)}`),
  listErrors: (params) => http.get(`/api/validation/errors${qs(params)}`),
  revalidateAll: () => http.post("/api/validation/re-validate-all"),

  // Alerts
  alerts: () => http.get("/api/alerts"),

  // Settings (rules)
  listRules: () => http.get("/api/settings/validation-rules"),
  createRule: (body) => http.post("/api/settings/validation-rules", body),
  updateRule: (id, body) => http.put(`/api/settings/validation-rules/${id}`, body),
  deleteRule: (id) => http.delete(`/api/settings/validation-rules/${id}`),
  resetRules: () => http.post("/api/settings/validation-rules/reset"),

  // Sync
  syncPending: () => http.get("/api/sync/pending"),
  syncPreview: (date, shift) =>
    http.get(`/api/sync/preview${qs({ production_date: date, shift })}`),
  syncSubmit: (date, shift, force) =>
    http.post("/api/sync/submit", { production_date: date, shift, force }),
  syncHistory: () => http.get("/api/sync/history"),
  getAutoSync: () => http.get("/api/sync/auto-sync"),
  setAutoSync: (body) => http.put("/api/sync/auto-sync", body),
  runSyncNow: () => http.post("/api/sync/run-now"),
};

export default api;
