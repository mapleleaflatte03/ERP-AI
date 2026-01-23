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
}

export interface Approval {
  id: string;
  job_id: string;
  tenant_id: string;
  proposal_id: string;
  status: string;
  requested_at: string;
  resolved_at?: string;
  resolved_by?: string;
}

export interface Forecast {
  id: string;
  tenant_id: string;
  forecast_date?: string;
  window_days: number;
  total_inflow: number;
  total_outflow: number;
  net_position: number;
  daily_forecast?: Array<{
    date: string;
    inflow: number;
    outflow: number;
    net: number;
  }>;
  created_at?: string;
}

export interface Simulation {
  id: string;
  tenant_id: string;
  base_forecast_id?: string;
  scenario_name?: string;
  assumptions?: {
    revenue_multiplier?: number;
    cost_multiplier?: number;
    payment_delay_days?: number;
  };
  baseline_net: number;
  projected_net: number;
  delta: number;
  percent_change: number;
  status?: string;
  created_at?: string;
  completed_at?: string;
}

export interface Finding {
  title: string;
  description: string;
  severity: string;
  metric_value?: string | number;
}

export interface Recommendation {
  action: string;
  rationale: string;
  priority: string;
  expected_impact?: string;
}

export interface Reference {
  type: string;
  id: string;
}

export interface Insight {
  id: string;
  tenant_id: string;
  status: string;
  source_window_days?: number;
  summary?: string;
  error?: string;
  top_findings?: Finding[];
  recommendations?: Recommendation[];
  references?: Reference[];
  created_at?: string;
  completed_at?: string;
}

export interface Evidence {
  postgres?: Record<string, number>;
  minio?: {
    sample_keys: string[];
  };
  qdrant?: {
    points_count: number;
  };
  temporal?: {
    completed_jobs: number;
  };
  jaeger?: {
    services: string[];
  };
  mlflow?: {
    runs_count: number;
  };
}
