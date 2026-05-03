/**
 * API service layer using axios.
 * All API calls go through this module — centralised auth, error handling, and base URL.
 */
import axios, { AxiosError } from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

// ── Auth token injection ──────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Global error handler ──────────────────────────────────────
api.interceptors.response.use(
  (res) => res,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// ── Auth ──────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", new URLSearchParams({ username: email, password }), {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    }),
  register: (email: string, password: string, full_name: string) =>
    api.post("/auth/register", { email, password, full_name }),
  me: () => api.get("/auth/me"),
};

// ── Resumes ───────────────────────────────────────────────────
export const resumeApi = {
  list: (page = 1, pageSize = 20, status?: string) =>
    api.get("/resumes/", { params: { page, page_size: pageSize, status } }),

  get: (id: string) => api.get(`/resumes/${id}`),

  getStatus: (id: string) => api.get(`/resumes/${id}/status`),

  upload: (file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/resumes/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    });
  },

  batchUpload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return api.post("/resumes/batch-upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  delete: (id: string) => api.delete(`/resumes/${id}`),
};

// ── Jobs ──────────────────────────────────────────────────────
export const jobApi = {
  list: (page = 1, pageSize = 20) =>
    api.get("/jobs/", { params: { page, page_size: pageSize } }),

  get: (id: string) => api.get(`/jobs/${id}`),

  create: (data: {
    title: string;
    company?: string;
    description: string;
    required_skills: string[];
    preferred_skills: string[];
    required_experience_years?: number;
    required_education?: string;
    location?: string;
  }) => api.post("/jobs/", data),

  update: (id: string, data: object) => api.put(`/jobs/${id}`, data),

  delete: (id: string) => api.delete(`/jobs/${id}`),

  reEmbed: (id: string) => api.post(`/jobs/${id}/embed`),
};

// ── Applications / Rankings ───────────────────────────────────
export const applicationApi = {
  create: (resume_id: string, job_id: string) =>
    api.post("/applications/", { resume_id, job_id }),

  batchApply: (job_id: string, resume_ids: string[]) =>
    api.post("/applications/batch", { job_id, resume_ids }),

  getRankings: (jobId: string, page = 1, pageSize = 20, minScore = 0) =>
    api.get(`/applications/job/${jobId}/rankings`, {
      params: { page, page_size: pageSize, min_score: minScore },
    }),

  get: (id: string) => api.get(`/applications/${id}`),

  rescore: (id: string) => api.post(`/applications/${id}/score`),

  updateStatus: (id: string, status: string) =>
    api.patch(`/applications/${id}/status`, null, { params: { new_status: status } }),
};

// ── Admin ─────────────────────────────────────────────────────
export const adminApi = {
  stats: () => api.get("/admin/stats"),
  users: () => api.get("/admin/users"),
  duplicates: () => api.get("/admin/duplicates"),
  rescoreAll: (jobId: string) => api.post(`/admin/rescore-all/${jobId}`),
  systemHealth: () => api.get("/admin/system-health"),
};
