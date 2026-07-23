export type ScientificVerdict =
  | "PASS"
  | "FAIL"
  | "NEEDS MANUAL REVIEW"
  | "PENDING"
  | "NOT_RUN";
export type OperationalState =
  | "QUEUED"
  | "RUNNING"
  | "BLOCKED"
  | "SUCCEEDED"
  | "FAILED_OPERATIONAL"
  | "CANCEL_REQUESTED"
  | "CANCELLED"
  | "NOT_QUEUED";

export interface WizardStep {
  number: number;
  label: string;
  complete: boolean;
  available: boolean;
}

export interface DraftSummary {
  campaign_id: string;
  title: string;
  instrument?: string;
  timeframe?: string;
  wizard_step?: number;
  updated_at?: string;
  frozen?: boolean;
  workflow_status?: string;
}

export interface CampaignSummary extends DraftSummary {
  lifecycle?: string;
  studio_managed?: boolean;
  workflow_blocker?: string | null;
  verdict?: ScientificVerdict;
  current_attempt?: string;
}

export interface DraftView {
  campaign_id: string;
  wizard_step: number;
  updated_at?: string;
  frozen_draft_sha256?: string | null;
  draft: Record<string, any>;
  state: Record<string, any>;
  steps: WizardStep[];
  validation?: Record<string, any> | null;
  matches?: DuplicateMatch[];
  review?: DuplicateReview | null;
}

export interface DuplicateMatch {
  campaign_id: string;
  title?: string;
  source?: string;
  lifecycle?: string;
  score?: number;
  similarity?: number;
  match_reasons?: string[];
  hypothesis?: string;
  expected_mechanism?: string;
}

export interface DuplicateReview {
  reviewed_campaign_ids: string[];
  conclusion: "distinct" | "duplicate" | "needs_review";
  substantive_distinction: string;
}

export interface DatasetSummary {
  dataset_id: string;
  symbol?: string;
  timeframe?: string;
  quality_verdict?: ScientificVerdict | string;
  coverage_start?: string;
  coverage_end?: string;
  row_count?: number;
  dropped_row_count?: number;
  gap_count?: number;
  duplicate_count?: number;
  out_of_order_count?: number;
  invalid_ohlc_count?: number;
  cadence_violation_count?: number;
  timezone?: string;
  timestamp_semantics?: string;
  roll_policy?: string;
  [key: string]: unknown;
}

export interface ModuleSummary {
  name: string;
  module_type?: string;
  summary?: string;
  decision_timing?: string;
  next_bar_entry?: boolean;
  certification?: string;
  certification_status?: string;
  implementation_version?: number;
  implementation_sha256?: string;
  certification_manifest_sha256?: string;
  required_test_categories?: string[];
  required_tests?: string[];
  strategy_package?: boolean;
  parameters?: Record<string, unknown>;
}

export interface JobRecord {
  job_id: string;
  job_type?: string;
  campaign_id?: string;
  variant_id?: string;
  payload?: Record<string, any>;
  state: OperationalState;
  operational_state?: OperationalState;
  research_verdict?: ScientificVerdict | null;
  attempt_reserved?: boolean;
  blocked_reason?: string | null;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
  started_at?: string;
  heartbeat_at?: string;
  finished_at?: string;
  progress?: number;
  progress_detail?: {
    phase: string;
    message: string;
    percent: number;
    completed?: number | null;
    total?: number | null;
    unit?: string | null;
    phase_started_at?: string;
    updated_at?: string;
    elapsed_seconds?: number | null;
    eta_seconds?: number | null;
  } | null;
}

export interface ReviewTask {
  id?: string;
  review_id?: string;
  type?: "mechanics" | "candidate" | string;
  campaign_id?: string;
  campaign_title?: string;
  variant_id?: string;
  attempt_id?: string;
  status?: string;
  blocker?: string;
  progress?: number;
  completed_samples?: number;
  required_samples?: number;
  next_action?: string;
  [key: string]: unknown;
}

export interface ResultCriterion {
  stage?: string;
  metric?: string;
  operator?: string;
  threshold?: unknown;
  actual?: unknown;
  result?: ScientificVerdict | string;
  reason?: string | null;
  evidence_path?: string | null;
}

export interface VariantResult {
  variant_id?: string;
  variant?: string;
  title?: string;
  research_verdict?: ScientificVerdict | string;
  verdict?: ScientificVerdict | string;
  operational_state?: OperationalState | string;
  first_failed_gate?: string;
  failed_stage?: string;
  stage_criteria?: ResultCriterion[];
  metrics?: Record<string, any>;
  [key: string]: unknown;
}

export interface CampaignDetail extends CampaignSummary {
  variants?: Array<Record<string, any>>;
  results?: VariantResult[];
  result_matrix?: VariantResult[];
  attempts?: Array<Record<string, any>>;
  protocol?: Record<string, any>;
  next_action?: string;
}

export interface StudioSettings {
  reviewer_identity?: string;
  default_commission_per_contract?: number;
  default_slippage_ticks?: number;
  default_initial_balance?: number;
  default_flatten_time?: string;
  openai_model?: string;
  openai_retention_notice?: string;
  openai_zero_data_retention_enabled?: boolean;
  privacy_notice_acknowledged?: boolean;
}

export interface LibrariesResponse {
  datasets: DatasetSummary[];
  modules: ModuleSummary[];
  prop_profiles?: Array<Record<string, any>>;
  recipes?: Array<Record<string, any>>;
}

export interface BootstrapResponse {
  workspace?: {
    name?: string;
    project_name?: string;
    path?: string;
    healthy?: boolean;
  };
  drafts: DraftSummary[];
  campaigns: CampaignSummary[];
  reviews: ReviewTask[];
  jobs: JobRecord[];
  libraries?: LibrariesResponse;
  settings?: StudioSettings;
  counts?: Record<string, number>;
  attention?: Array<Record<string, any>>;
}

export interface ApiErrorShape {
  detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>;
  message?: string;
  errors?: Array<{ field?: string; message?: string }>;
}
