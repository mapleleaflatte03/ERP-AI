// Document types for accounting
export type DocumentStatus = 
  | 'new' 
  | 'extracting' 
  | 'extracted' 
  | 'proposing'
  | 'proposed' 
  | 'pending_approval' 
  | 'approved' 
  | 'rejected' 
  | 'posted';

export type DocumentType = 
  | 'invoice' 
  | 'receipt' 
  | 'bank_statement' 
  | 'contract'
  | 'payment_voucher'
  | 'other';

export interface Document {
  id: string;
  filename: string;
  type: DocumentType;
  status: DocumentStatus;
  vendor_name?: string;
  vendor_tax_id?: string;
  invoice_no?: string;
  invoice_date?: string;
  total_amount?: number;
  vat_amount?: number;
  currency?: string;
  extracted_fields?: Record<string, any>;
  extracted_text?: string;
  file_url?: string;
  created_at: string;
  updated_at: string;
  job_id?: string;
}

export interface JournalEntryLine {
  id?: string;
  debit_account?: string;
  debit_account_name?: string;
  credit_account?: string;
  credit_account_name?: string;
  amount: number;
  description?: string;
  object_code?: string;  // Mã đối tượng (khách hàng/NCC)
  object_name?: string;
  cost_center?: string;
  confidence?: number;
  reasoning?: string;  // Giải thích tại sao chọn tài khoản
}

export interface JournalProposal {
  id: string;
  document_id: string;
  entries: JournalEntryLine[];
  journal_lines?: JournalEntryLine[];  // Alias for backward compatibility
  total_debit: number;
  total_credit: number;
  is_balanced: boolean;
  description?: string;
  posting_date?: string;
  created_at: string;
  status: 'draft' | 'pending' | 'approved' | 'rejected';
}

export interface Approval {
  id: string;
  document_id: string;
  proposal_id: string;
  document?: Document;
  proposal?: JournalProposal;
  status: 'pending' | 'approved' | 'rejected';
  reviewer?: string;
  reviewer_note?: string;
  created_at: string;
  resolved_at?: string;
  // For backward compatibility with old Approvals.tsx
  job_id?: string;
  filename?: string;
  vendor_name?: string;
  total_amount?: number;
  reason?: string;
}

export interface EvidenceEvent {
  id: string;
  document_id: string;
  job_id?: string;
  action: string;
  timestamp: string;  // When the event occurred
  actor: string;  // user:email or agent:name
  payload?: Record<string, any>;  // Additional metadata
  // Legacy fields for backward compatibility
  step?: string;
  input_summary?: string;
  output_summary?: string;
  severity?: 'info' | 'warning' | 'error' | 'success';
  details?: Record<string, any>;
  trace_id?: string;
  created_at?: string;
}

export interface BankTransaction {
  id: string;
  date: string;
  description: string;
  amount: number;
  type: 'credit' | 'debit';
  reference?: string;
  matched_document_id?: string;
  status: 'unmatched' | 'matched' | 'suspicious';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
  created_at: string;
}

// Legacy types for backward compatibility
export interface Job {
  job_id: string;
  tenant_id: string;
  status: string;
  document_id?: string;
  extracted_invoice_id?: string;
  journal_proposal_id?: string;
  ledger_entry_id?: string;
  approval_id?: string;
  temporal_workflow_id?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
  filename?: string;
  document_type?: string;
  completed_at?: string;
  error?: string;
  result?: any;
  proposal?: any;
}

export interface TestbenchTool {
  id: string;
  name: string;
  description: string;
}

export interface TestbenchResult {
  tool: string;
  name: string;
  passed: boolean;
  latency_ms: number;
  summary: string;
  evidence: any;
  trace_id?: string;
  warning?: string;
}
