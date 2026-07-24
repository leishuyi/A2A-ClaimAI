export interface Case {
  id: number;
  case_no: string;
  insured_name: string;
  insurance_product: string;
  incident_desc: string;
  incident_date: string;
  status: CaseStatus;
  risk_level: RiskLevel;
  total_amount: number | null;
  calculated_amount: number | null;
  created_at: string;
  updated_at: string;
}

export type CaseStatus =
  | 'draft'
  | 'processing'
  | 'agents_completed'
  | 'pending_review'
  | 'approved'
  | 'rejected';

export type RiskLevel = 'low' | 'medium' | 'high';

export interface CaseCreate {
  insured_name: string;
  insurance_product: string;
  incident_desc: string;
  incident_date: string;
  total_amount?: number | null;
  documents?: DocumentUpload[];
}

export interface DocumentUpload {
  doc_type: string;
  content_text: string;
}

export interface Document {
  id: number;
  case_id: number;
  doc_type: DocType;
  file_name: string;
  file_size: number;
  mime_type: string | null;
  url: string;
  created_at: string;
}

export type DocType = 'id_card' | 'diagnosis' | 'invoice' | 'medical_record' | 'other';

export const DocTypeLabels: Record<DocType, string> = {
  id_card: '身份证',
  diagnosis: '诊断证明',
  invoice: '费用发票',
  medical_record: '住院病历',
  other: '其他',
};

export interface AgentTrace {
  id: number;
  case_id: number;
  agent_name: string;
  agent_label: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  confidence: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ReviewRequest {
  action: 'approve' | 'reject' | 'modify';
  comment: string;
  operator: string;
  modified_amount?: number;
}

export interface ReviewResponse {
  id: number;
  case_id: number;
  action: string;
  comment: string;
  operator: string;
  created_at: string;
}
