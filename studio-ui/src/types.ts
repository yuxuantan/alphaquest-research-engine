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
  workflow_context?: Record<string, any>;
  research_progress?: ResearchProgress;
  integrity_status?: string;
}

export type ResearchStageStatus =
  | "complete"
  | "current"
  | "ready"
  | "upcoming"
  | "locked"
  | "failed"
  | "blocked"
  | "not_applicable";

export interface ResearchStage {
  id: string;
  label: string;
  phase: string;
  description: string;
  step: number;
  status: ResearchStageStatus;
}

export interface VariantProgress {
  variant_id: string;
  attempt_id?: string | null;
  is_current: boolean;
  current_step: number;
  total_steps: number;
  current_stage_id: string;
  current_stage_label: string;
  current_phase: string;
  scientific_status: ScientificVerdict | string;
  operational_state: OperationalState | string;
  next_action: string;
  stages: ResearchStage[];
}

export interface ResearchProgress {
  campaign?: VariantProgress | null;
  variants: VariantProgress[];
  flow_definition?: Array<Omit<ResearchStage, "step" | "status">>;
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
  exact_fingerprint?: boolean;
  taxonomy_schema?: string;
  taxonomy_score?: number;
  match_band?: string;
  matched_dimensions?: string[];
  dimension_scores?: Record<string, number>;
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
  display_name?: string;
  source_type?: string;
  storage_format?: string;
  exchange_timezone?: string;
  quality_notes?: string[];
  capabilities?: string[];
  research_readiness?: {
    status: string;
    required_months: number;
    available_months?: number | null;
    blockers: string[];
    limitations: string[];
  };
  used_by?: Array<{
    campaign_id: string;
    campaign_title: string;
    variant_id: string;
  }>;
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
  certification_current?: boolean;
  certification_errors?: string[];
  active_strategy_package?: boolean;
  available_for_publication?: boolean;
  strategy_label?: string;
  strategy_description?: string;
  implementation_version?: number;
  implementation_sha256?: string;
  certification_manifest_sha256?: string;
  required_test_categories?: string[];
  required_tests?: string[];
  strategy_package?: boolean;
  parameters?: Record<string, unknown>;
  used_by?: Array<{
    campaign_id: string;
    campaign_title: string;
    variant_id: string;
  }>;
}

export interface JobRecord {
  job_id: string;
  job_type?: string;
  campaign_id?: string;
  variant_id?: string;
  attempt_id?: string;
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
    active_workers?: number | null;
    expected_workers?: number | null;
    phase_started_at?: string;
    work_started_at?: string | null;
    updated_at?: string;
    elapsed_seconds?: number | null;
    work_elapsed_seconds?: number | null;
    eta_seconds?: number | null;
    throughput_per_hour?: number | null;
    estimated_finish_at?: string | null;
    parallelism_warning?: string | null;
  } | null;
}

export type CodexAvailabilityState =
  | "AVAILABLE"
  | "NOT_INSTALLED"
  | "AUTH_REQUIRED"
  | "WRONG_AUTH_MODE"
  | "UNAVAILABLE";

export interface CodexAvailability {
  schema?: "alphaquest.codex-availability/v1" | string;
  status: CodexAvailabilityState | string;
  executable_available: boolean;
  authenticated?: boolean | null;
  authentication_mode?: "CHATGPT" | "API_KEY" | "UNKNOWN" | string | null;
  version?: string | null;
  checked_at?: string;
  detail?: string;
}

export type CodexTaskState =
  | "WAITING_FOR_CODEX"
  | "RUNNING"
  | "PROPOSAL_READY"
  | "FAILED"
  | "PAUSED"
  | "CANCEL_REQUESTED"
  | "CANCELLED";

export interface CodexTaskRecord {
  schema?: "alphaquest.codex-task-record/v1" | string;
  task_id: string;
  idempotency_key?: string;
  submission_sha256?: string;
  request?: {
    schema?: string;
    task_type?: string;
    input_hashes?: Record<string, string>;
  };
  task_type?: string;
  campaign_id?: string | null;
  factory_task_id?: string;
  state: CodexTaskState | string;
  worker_id?: string | null;
  run_count?: number;
  max_runs?: number;
  proposal?: Record<string, unknown> | null;
  proposal_validation?: {
    status?: string;
    error?: string | null;
    [key: string]: unknown;
  } | null;
  proposal_disposition?: {
    status?: string;
    reviewer?: string;
    notes?: string;
    recorded_at?: string;
    campaign_mutations_performed?: boolean;
    approval_granted?: boolean;
    [key: string]: unknown;
  } | null;
  structured_review?: {
    status?: string;
    artifact_sha256?: string | null;
    reviewer?: string | null;
    recorded_at?: string | null;
  } | null;
  selected_action?: {
    selected_action?:
      | "ABANDON_EDGE"
      | "PROPOSE_SUCCESSOR"
      | "START_NEW_RESEARCH_GENERATION"
      | "ASSESS_OTHER_DESTINATION"
      | "STOP_NO_FRESH_HOLDOUT"
      | string;
    selected_rank?: number;
    reviewer?: string;
    notes?: string;
    selection_sha256?: string;
    recorded_at?: string;
    campaign_mutations_performed?: boolean;
    approval_granted?: boolean;
    [key: string]: unknown;
  } | null;
  selected_action_completion?: {
    decision_id?: string;
    selected_action?: "ABANDON_EDGE" | "STOP_NO_FRESH_HOLDOUT" | string;
    terminal_status?: string;
    reviewer?: string;
    notes?: string;
    completion_sha256?: string;
    recorded_at?: string;
    completed?: boolean;
    scientific_verdict_changed?: boolean;
    [key: string]: unknown;
  } | null;
  applied?: boolean;
  approved?: boolean;
  failure_kind?: string | null;
  error?: string | null;
  pause_reason?: string | null;
  created_at?: string;
  updated_at?: string;
  started_at?: string | null;
  heartbeat_at?: string | null;
  cancellation_requested_at?: string | null;
  finished_at?: string | null;
}

export interface FactoryNextAction {
  kind?: string;
  task_type?: string;
  campaign_id?: string | null;
  label?: string;
  detail?: string;
  eligible?: boolean;
  requires_human_review?: boolean;
  blocked_reason?: string | null;
  href?: string;
}

export interface FactoryStatus {
  schema?: string;
  enabled: boolean;
  availability: CodexAvailability;
  factory_state?: string;
  paused: boolean;
  pause_reason?: string | null;
  queue_counts?: Record<string, number>;
  active_task?: CodexTaskRecord | null;
  latest_task?: CodexTaskRecord | null;
  next_action?: FactoryNextAction | string | null;
  legacy_openai_api_available?: boolean;
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
  decision_role?: "scientific_validity" | "generic_objective" | null;
}

export interface VariantResult {
  variant_id?: string;
  variant?: string;
  title?: string;
  research_verdict?: ScientificVerdict | string;
  scientific_validity_verdict?: ScientificVerdict | string;
  generic_objective_verdict?: ScientificVerdict | string;
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
  mechanics?: Record<string, any>;
  workflow_context?: Record<string, any>;
  attempt_results?: Record<string, Record<string, VariantResult>>;
  next_action?: string;
}

export interface StudioSettings {
  reviewer_identity?: string;
  assistant_mode?:
    | "codex_subscription"
    | "manual_only"
    | "legacy_openai_api";
  codex_timeout_seconds?: number;
  codex_max_runs_per_day?: number;
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
  account_profiles?: Array<Record<string, any>>;
  recipes?: Array<Record<string, any>>;
  execution_profiles?: Array<Record<string, any>>;
}

export interface BootstrapResponse {
  workspace?: {
    name?: string;
    project_name?: string;
    path?: string;
    healthy?: boolean;
    diagnostics?: Record<string, any>;
  };
  drafts: DraftSummary[];
  campaigns: CampaignSummary[];
  reviews: ReviewTask[];
  jobs: JobRecord[];
  libraries?: LibrariesResponse;
  settings?: StudioSettings;
  counts?: Record<string, number>;
  attention?: Array<Record<string, any>>;
  indexed_attention?: ReviewTask[];
  workflow_actions?: Array<{
    priority: number;
    kind: string;
    campaign_id: string;
    label: string;
    detail: string;
    href: string;
  }>;
}

export interface ApiErrorShape {
  detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>;
  message?: string;
  errors?: Array<{ field?: string; message?: string }>;
}
