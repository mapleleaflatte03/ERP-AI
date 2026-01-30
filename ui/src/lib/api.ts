import axios from 'axios';
import type { AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Load token from localStorage
    this.token = localStorage.getItem('erpx_token');

    // Request interceptor to add auth header
    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`;
      }
      return config;
    });

    // Response interceptor for error handling (Phase 6 - Fix C)
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        const status = error.response?.status;
        let message = "Có lỗi xảy ra, vui lòng thử lại sau.";

        if (status === 401) {
          this.clearToken();
          message = "Phiên làm việc hết hạn. Vui lòng đăng nhập lại.";
        } else if (status === 403) {
          message = "Bạn không có quyền thực hiện hành động này.";
        } else if (status === 404) {
          message = "Không tìm thấy dữ liệu yêu cầu.";
        } else if (status === 500) {
          message = "Lỗi hệ thống (500). Vui lòng liên hệ quản trị viên.";
        } else if (!error.response) {
          message = "Không thể kết nối đến máy chủ. Kiểm tra mạng của bạn.";
        }

        // Attach localized message for UI use
        if (error.response) error.response.data = { ...error.response.data, ui_message: message };
        return Promise.reject(error);
      }
    );
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('erpx_token', token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('erpx_token');
  }

  getToken() {
    return this.token;
  }

  isAuthenticated() {
    return !!this.token;
  }

  // Auth
  async login(username: string, password: string): Promise<{ access_token: string }> {
    const keycloakUrl = import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8180';
    const response = await axios.post(
      `${keycloakUrl}/realms/erpx/protocol/openid-connect/token`,
      new URLSearchParams({
        grant_type: 'password',
        client_id: 'erpx-api',
        username,
        password,
      }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    );
    return response.data;
  }

  // Health
  async getHealth() {
    const response = await this.client.get('/health');
    return response.data;
  }

  // Testbench
  async getTestbenchTools() {
    const response = await this.client.get('/v1/testbench/tools');
    return response.data;
  }

  async runTestbenchTool(tool: string) {
    const response = await this.client.post('/v1/testbench/run', { tool });
    return response.data;
  }

  // =====================================================
  // Documents API (for accounting app)
  // =====================================================

  async getDocuments(params?: Record<string, string>) {

    const response = await this.client.get('/v1/documents', { params: params || {} });
    return response.data;
  }

  async getDocument(documentId: string) {
    const response = await this.client.get(`/v1/documents/${documentId}`);
    return response.data;
  }

  async deleteDocument(documentId: string) {
    const response = await this.client.delete(`/v1/documents/${documentId}`);
    return response.data;
  }

  async uploadDocument(file: File, tenantId: string = 'default') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tenant_id', tenantId);
    const response = await this.client.post('/v1/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  async runExtraction(documentId: string) {
    const response = await this.client.post(`/v1/documents/${documentId}/extract`);
    return response.data;
  }

  async runProposal(documentId: string) {
    const response = await this.client.post(`/v1/documents/${documentId}/propose`);
    return response.data;
  }

  async getDocumentProposal(documentId: string) {
    const response = await this.client.get(`/v1/documents/${documentId}/proposal`);
    return response.data;
  }

  async getDocumentEvidence(documentId: string) {
    const response = await this.client.get(`/v1/documents/${documentId}/evidence`);
    return response.data;
  }

  async getFileBlob(url: string) {
    const response = await this.client.get(url, { responseType: 'blob' });
    return response.data;
  }

  // Get file preview as text/HTML (for Excel preview)
  async getFilePreview(url: string): Promise<string> {
    const response = await this.client.get(url, { responseType: 'text' });
    return response.data as string;
  }

  // =====================================================
  // Approvals API (for accounting app)
  // =====================================================

  async getApprovals(status?: string, limit: number = 20, offset: number = 0) {
    const params: Record<string, string | number> = { limit, offset };
    if (status) params.status = status;

    const response = await this.client.get('/v1/approvals', { params });
    return response.data;
  }

  async submitApproval(documentId: string, proposalId: string) {
    const response = await this.client.post(`/v1/documents/${documentId}/submit`, {
      proposal_id: proposalId,
    });
    return response.data;
  }

  async getDocumentLedger(documentId: string) {
    const response = await this.client.get(`/v1/documents/${documentId}/ledger`);
    return response.data;
  }

  async approveDocument(approvalId: string, note?: string) {
    const response = await this.client.post(`/v1/approvals/${approvalId}/approve`, {
      user_id: 'ui-user',
      note,
    });
    return response.data;
  }

  async rejectDocument(approvalId: string, reason: string) {
    const response = await this.client.post(`/v1/approvals/${approvalId}/reject`, {
      user_id: 'ui-user',
      reason,
    });
    return response.data;
  }

  // =====================================================
  // Copilot Chat API
  // =====================================================

  async sendCopilotMessage(message: string, context?: Record<string, any>) {
    const response = await this.client.post('/v1/copilot/chat', {
      message,
      context,
    });
    return response.data;
  }

  // =====================================================
  // Legacy API (keep for backward compatibility)
  // =====================================================

  // Jobs
  async getJob(jobId: string) {
    const response = await this.client.get(`/v1/jobs/${jobId}`);
    return response.data;
  }

  async getJobStatus(jobId: string) {
    const response = await this.client.get(`/v1/jobs/${jobId}`);
    return response.data;
  }

  async listJobs(limit: number = 20) {
    const response = await this.client.get(`/v1/jobs?limit=${limit}`);
    return response.data;
  }

  async getJobEvidence(jobId: string) {
    const response = await this.client.get(`/v1/jobs/${jobId}/evidence`);
    return response.data;
  }

  async getJobTimeline(jobId: string) {
    const response = await this.client.get(`/v1/jobs/${jobId}/timeline`);
    return response.data;
  }

  async getJobPolicy(jobId: string) {
    const response = await this.client.get(`/v1/jobs/${jobId}/policy`);
    return response.data;
  }

  async getJobState(jobId: string) {
    const response = await this.client.get(`/v1/jobs/${jobId}/state`);
    return response.data;
  }

  async getJobZones(jobId: string) {
    const response = await this.client.get(`/v1/jobs/${jobId}/zones`);
    return response.data;
  }

  // Legacy Approvals
  async listPendingApprovals() {
    const response = await this.client.get('/v1/approvals/pending');
    return response.data;
  }

  async approveProposal(approvalId: string, userId: string = 'ui-user') {
    const response = await this.client.post(`/v1/approvals/${approvalId}/approve`, {
      user_id: userId,
    });
    return response.data;
  }

  async rejectProposal(approvalId: string, userId: string = 'ui-user', reason: string = '') {
    const response = await this.client.post(`/v1/approvals/${approvalId}/reject`, {
      user_id: userId,
      reason,
    });
    return response.data;
  }

  async approveByJobId(jobId: string, userId: string = 'ui-user') {
    const response = await this.client.post(`/v1/jobs/${jobId}/approve`, {
      user_id: userId,
    });
    return response.data;
  }

  async rejectByJobId(jobId: string, userId: string = 'ui-user', reason: string = '') {
    const response = await this.client.post(`/v1/jobs/${jobId}/reject`, {
      user_id: userId,
      reason,
    });
    return response.data;
  }

  // Evidence
  async getEvidence() {
    const response = await this.client.get('/v1/evidence/summary');
    return response.data;
  }

  async getGlobalTimeline(limit: number = 50) {
    const response = await this.client.get('/v1/evidence/timeline', { params: { limit } });
    return response.data;
  }

  // =====================================================
  // Reports API
  // =====================================================

  async getGeneralLedger(startDate: string, endDate: string) {
    const response = await this.client.get('/v1/reports/general-ledger', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  }

  async getReportTimeseries(startDate: string, endDate: string) {
    const response = await this.client.get('/v1/reports/timeseries', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  }

  // ========================================================
  // Journal Proposals API (list all proposals)
  // Uses direct path without /api prefix for unauthenticated access
  // ========================================================

  async getJournalProposals(status?: string, limit: number = 50, offset: number = 0) {
    const params: Record<string, string | number> = { limit, offset };
    if (status) params.status = status;
    // Use axios directly with absolute path (no /api prefix)
    const response = await axios.get('/v1/journal-proposals', { params });
    return response.data;
  }
}

export const api = new ApiClient();
export default api;
