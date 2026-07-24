import type { Case, CaseCreate, AgentTrace, ReviewRequest, ReviewResponse, Document } from '../types';

const BASE = '/api/v1';

interface ApiError {
  code: number;
  message: string;
  data?: unknown;
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  const body = await res.json();

  // BizError 统一处理（HTTP 200 + 业务码）
  if (body && typeof body === 'object' && 'code' in body && body.code !== 0) {
    throw new Error((body as ApiError).message || '业务处理失败');
  }

  return body as T;
}

/** 分页列表响应 */
export interface PageResult<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

/** 上传文件到案件（使用 FormData，非 JSON） */
async function uploadFile<T>(caseId: number, file: File, docType: string, onProgress?: (pct: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE}/${caseId}/documents`);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };

    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        if (body && body.code !== 0) {
          reject(new Error(body.message || '上传失败'));
        } else {
          resolve(body as T);
        }
      } catch {
        reject(new Error('解析响应失败'));
      }
    };

    xhr.onerror = () => reject(new Error('网络错误'));

    const formData = new FormData();
    formData.append('file', file);
    formData.append('doc_type', docType);
    xhr.send(formData);
  });
}

export const api = {
  // Cases
  getCases: (params?: { page?: number; page_size?: number; status?: string }) => {
    const q = new URLSearchParams();
    if (params?.page) q.set('page', String(params.page));
    if (params?.page_size) q.set('page_size', String(params.page_size));
    if (params?.status) q.set('status', params.status);
    return request<PageResult<Case>>(`/cases?${q}`);
  },
  getCase: (id: number) => request<Case>(`/cases/${id}`),
  createCase: (data: CaseCreate) => request<Case>('/cases', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Agents
  runAgents: (caseId: number) => request<{ message: string; case: Case }>(`/${caseId}/run`, {
    method: 'POST',
  }),
  getTraces: (caseId: number) => request<AgentTrace[]>(`/${caseId}/traces`),

  // Human Gate
  getReview: (caseId: number) => request<ReviewResponse[]>(`/${caseId}/review`),
  submitReview: (caseId: number, data: ReviewRequest) => request<ReviewResponse>(`/${caseId}/review`, {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  // Documents
  getDocuments: (caseId: number) => request<Document[]>(`/${caseId}/documents`),
  uploadDocument: (caseId: number, file: File, docType: string, onProgress?: (pct: number) => void) =>
    uploadFile<{ data: Document }>(caseId, file, docType, onProgress),
  deleteDocument: (caseId: number, docId: number) =>
    request<void>(`/${caseId}/documents/${docId}`, { method: 'DELETE' }),
};
