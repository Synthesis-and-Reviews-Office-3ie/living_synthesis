import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
console.log("[API] Base URL:", API_URL);

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    console.log("[API] Request to:", config.url, "Token:", token ? "present" : "missing");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle 401 errors - but don't redirect immediately for better error UX
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        // Only clear token, let the component handle redirect/error display
        localStorage.removeItem("token");
        // Don't redirect here - let the component show the error first
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  signup: (email: string, password: string, name?: string) =>
    api.post("/auth/signup", { email, password, name }),
  
  login: async (email: string, password: string) => {
    const response = await api.post("/auth/login", { email, password });
    const { access_token } = response.data;
    localStorage.setItem("token", access_token);
    return response;
  },
  
  logout: () => {
    localStorage.removeItem("token");
  },
  
  getProfile: () => api.get("/auth/me"),
  
  updateProfile: async (data: { name?: string; email?: string; preferred_llm_model?: string }) => {
    const response = await api.put("/auth/me", data);
    return response.data;
  },
  
  getAvailableModels: async () => {
    const response = await api.get("/auth/models");
    return response.data;
  },
  
  requestPasswordReset: (email: string) =>
    api.post("/auth/password-reset/request", { email }),
  
  confirmPasswordReset: (token: string, new_password: string) =>
    api.post("/auth/password-reset/confirm", { token, new_password }),
};

// Topics API
export const topicsApi = {
  list: () => api.get("/topics"),
  
  get: (id: string) => api.get(`/topics/${id}`),
  
  create: (data: {
    name: string;
    description?: string;
    queries: Record<string, string>;
    frequency?: "daily" | "weekly";
  }) => api.post("/topics", data),
  
  update: (id: string, data: {
    name?: string;
    description?: string;
    queries?: Record<string, string>;
    frequency?: "daily" | "weekly";
    is_active?: boolean;
    living_review_enabled?: boolean;
    living_review_type?: string;
    living_review_source?: string;
  }) => api.put(`/topics/${id}`, data),
  
  delete: (id: string) => api.delete(`/topics/${id}`),
  
  // Run paper search
  run: (id: string) => api.post(`/topics/${id}/run`),
  
  // Run historical search (no date limit, one-time only)
  runHistorical: (id: string) => api.post(`/topics/${id}/run-historical`),
  
  // Get topic stats (analytics)
  getStats: (id: string) => api.get(`/topics/${id}/stats`),
  
  getReviewQueue: (id: string) => api.get(`/topics/${id}/review`),
  
  reviewPaper: (topicId: string, paperId: string, included: boolean) => 
    api.post(`/topics/${topicId}/papers/${paperId}/review`, { included }),
  
  // AI Summary generation
  summarizePaper: (topicId: string, paperId: string) =>
    api.post(`/topics/${topicId}/papers/${paperId}/summarize`),
  
  summarizeAll: (topicId: string) =>
    api.post(`/topics/${topicId}/summarize-all`),

  // LLM Relevance Scoring
  scoreRelevance: (topicId: string) =>
    api.post(`/topics/${topicId}/score-relevance`),
  
  getFilteredReviewQueue: (topicId: string, minRelevance: number = 0, hideLowRelevance: boolean = false) =>
    api.get(`/topics/${topicId}/review-filtered`, { params: { min_relevance: minRelevance, hide_low_relevance: hideLowRelevance } }),

  submitReview: (id: string, decisions: Array<{
    paper_id: string;
    include: boolean;
    reviewer_notes?: string;
  }>) => api.put(`/topics/${id}/review`, { decisions }),
  
  generateNewsletter: (id: string) => api.post(`/topics/${id}/generate`),
  
  // Weekly AI Digest
  generateDigest: (topicId: string) => api.post(`/topics/${topicId}/generate-digest`),
  
  // Trash management
  getTrash: (topicId: string) => api.get(`/topics/${topicId}/trash`),
  restorePaper: (topicId: string, paperId: string) => api.post(`/topics/${topicId}/papers/${paperId}/restore`),
  
  getNewsletters: (id: string) => api.get(`/topics/${id}/newsletters`),
};

// Newsletters API
export const newslettersApi = {
  list: (topicId: string) => api.get(`/topics/${topicId}/newsletters`),
  get: (topicId: string, id: string) => api.get(`/topics/${topicId}/newsletters/${id}`),
  generate: (topicId: string) => api.post(`/topics/${topicId}/newsletters/generate`),
};

// Billing API
export const billingApi = {
  createCheckout: (priceId: string) =>
    api.post("/billing/checkout", { price_id: priceId }),
  
  getPortalUrl: () => api.get("/billing/portal"),
};

// AI API
export const aiApi = {
  generateQueries: (description: string) =>
    api.post("/ai/generate-queries", { description }),
  
  testQuery: (query: string, source: string, limit: number = 5) =>
    api.post("/ai/test-query", { query, source, limit }),
};

// Types
export interface User {
  id: string;
  email: string;
  name?: string;
  tier: "free" | "pro" | "team";
  is_verified: boolean;
  created_at: string;
}

export interface Topic {
  id: string;
  name: string;
  description?: string;
  queries: Record<string, string>;
  frequency: "daily" | "weekly";
  is_active: boolean;
  created_at: string;
  last_run_at?: string;
  // Historical search (one-time, no date limit)
  historical_search_done?: boolean;
  // Living Review (Pro+)
  living_review_enabled?: boolean;
  living_review_type?: string;
  living_review_source?: string;
  living_review_last_sync?: string;
  // Displayed by the review pages; the API does not currently return it (renders as 0).
  papers_count?: number;
}

export interface Paper {
  id: string;
  doi?: string;
  external_id?: string;
  source: string;
  title: string;
  abstract?: string;
  publication_date?: string;
  oa_url?: string;
  is_oa: boolean;
}

export interface TopicPaper {
  id: string;
  paper: Paper;
  headline?: string;
  summary?: string;
  category?: string;
  models_mentioned?: string[];
  relevance_score?: number;
  include: boolean;
  reviewed_at?: string;
}

export interface Newsletter {
  id: string;
  topic_id: string;
  html_url?: string;
  pdf_url?: string;
  paper_count: number;
  sent_at?: string;
  opens: number;
  clicks: number;
  created_at: string;
  period_start?: string;
  period_end?: string;
}
