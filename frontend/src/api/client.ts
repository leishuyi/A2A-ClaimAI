import type { Case, CaseCreate, AgentTrace, ReviewRequest, ReviewResponse } from '../types';

const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  // Cases
  getCases: () => request<Case[]>('/cases'),
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
};
