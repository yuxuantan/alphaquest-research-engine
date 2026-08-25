import type {
  BootstrapResponse,
  CampaignDetail,
  CodexTaskRecord,
  DraftView,
  DuplicateReview,
  FactoryStatus,
  JobRecord,
  LibrariesResponse,
  ReviewTask,
  StudioSettings,
} from "./types";

export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;

  constructor(
    message: string,
    status = 0,
    fields: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  )
    headers.set("Content-Type", "application/json");
  headers.set("Accept", "application/json");
  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError(
      "Research Studio could not reach its local service. The worker continues independently.",
    );
  }
  const text = await response.text();
  const payload = text ? safeJson(text) : {};
  if (!response.ok) {
    const fields: Record<string, string> = {};
    if (Array.isArray(payload?.detail)) {
      for (const item of payload.detail) {
        fields[
          (item.loc || []).filter((part: unknown) => part !== "body").join(".")
        ] = item.msg || "Invalid value";
      }
    }
    if (Array.isArray(payload?.errors)) {
      for (const item of payload.errors)
        fields[item.field || "form"] = item.message || "Invalid value";
    }
    const message =
      typeof payload?.detail === "string"
        ? payload.detail
        : payload?.error?.message || payload?.message || response.statusText;
    throw new ApiError(
      message || "The governed action was rejected.",
      response.status,
      fields,
    );
  }
  return payload as T;
}

function safeJson(text: string): any {
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

const json = (value: unknown): string => JSON.stringify(value);

export const api = {
  bootstrap: () => request<BootstrapResponse>("/api/bootstrap"),
  createDraft: (value: {
    title: string;
    instrument: string;
    campaign_id?: string;
    research_objectives?: Record<string, unknown>;
  }) =>
    request<DraftView>("/api/drafts", { method: "POST", body: json(value) }),
  draft: (id: string) =>
    request<DraftView>(`/api/drafts/${encodeURIComponent(id)}`),
  saveBrief: (id: string, value: unknown) =>
    request<DraftView>(`/api/drafts/${encodeURIComponent(id)}/brief`, {
      method: "PUT",
      body: json(value),
    }),
  duplicateContext: (id: string) =>
    request<{
      matches: Array<Record<string, any>>;
      review: DuplicateReview | null;
    }>(`/api/drafts/${encodeURIComponent(id)}/duplicates`),
  saveDuplicates: (id: string, value: DuplicateReview) =>
    request<DraftView>(`/api/drafts/${encodeURIComponent(id)}/duplicates`, {
      method: "PUT",
      body: json(value),
    }),
  closeDuplicate: (id: string) =>
    request<Record<string, unknown>>(
      `/api/drafts/${encodeURIComponent(id)}/duplicates/close`,
      { method: "POST" },
    ),
  selectDataset: (id: string, dataset_id: string) =>
    request<DraftView>(`/api/drafts/${encodeURIComponent(id)}/dataset/select`, {
      method: "POST",
      body: json({ dataset_id }),
    }),
  saveExecution: (id: string, value: unknown) =>
    request<DraftView>(`/api/drafts/${encodeURIComponent(id)}/execution`, {
      method: "PUT",
      body: json(value),
    }),
  saveRecipe: (id: string, value: unknown) =>
    request<DraftView>(
      `/api/drafts/${encodeURIComponent(id)}/mechanics/recipe`,
      { method: "PUT", body: json(value) },
    ),
  saveRule: (id: string, value: unknown) =>
    request<DraftView>(`/api/drafts/${encodeURIComponent(id)}/mechanics/rule`, {
      method: "PUT",
      body: json(value),
    }),
  saveEventStrategy: (id: string, value: unknown) =>
    request<DraftView>(
      `/api/drafts/${encodeURIComponent(id)}/mechanics/event-strategy`,
      { method: "PUT", body: json(value) },
    ),
  saveHandoff: (id: string, value: unknown) =>
    request<DraftView>(
      `/api/drafts/${encodeURIComponent(id)}/mechanics/handoff`,
      { method: "PUT", body: json(value) },
    ),
  variants: (id: string) =>
    request<{
      variants: Array<Record<string, any>>;
      catalog: Array<Record<string, any>>;
      draft_context: Record<string, any>;
    }>(`/api/drafts/${encodeURIComponent(id)}/variants`),
  saveVariants: (id: string, variants: unknown[]) =>
    request<DraftView>(`/api/drafts/${encodeURIComponent(id)}/variants`, {
      method: "PUT",
      body: json({ variants }),
    }),
  freeze: (id: string) =>
    request<DraftView>(`/api/drafts/${encodeURIComponent(id)}/freeze`, {
      method: "POST",
      body: json({ confirmed: true }),
    }),
  publish: (id: string) =>
    request<Record<string, unknown>>(
      `/api/drafts/${encodeURIComponent(id)}/publish`,
      { method: "POST" },
    ),
  campaign: (id: string, refresh = false) =>
    request<{
      campaign: CampaignDetail;
      attempts: Array<Record<string, any>>;
      stage_matrix: Array<Record<string, any>>;
      latest_results: Record<string, any>;
      attempt_results: Record<string, Record<string, any>>;
      account_evaluations: Array<Record<string, any>>;
      workflow_context: Record<string, any>;
      recommended_action: string;
    }>(
      `/api/campaigns/${encodeURIComponent(id)}${
        refresh ? "?refresh=true" : ""
      }`,
    ),
  campaignResults: (id: string, refresh = false) =>
    request<{
      campaign_id: string;
      attempt_results: Record<string, Record<string, any>>;
      account_evaluations: Array<Record<string, any>>;
      partial_errors: Array<Record<string, string>>;
    }>(
      `/api/campaigns/${encodeURIComponent(id)}/results${
        refresh ? "?refresh=true" : ""
      }`,
    ),
  resultArtifactUrl: (
    campaignId: string,
    attemptId: string,
    variantId: string,
    artifactName: string,
  ) =>
    `/api/campaigns/${encodeURIComponent(campaignId)}/results/${encodeURIComponent(attemptId)}/${encodeURIComponent(variantId)}/artifacts/${encodeURIComponent(artifactName)}`,
  resultReportUrl: (
    campaignId: string,
    attemptId: string,
    variantId: string,
  ) =>
    `/api/campaigns/${encodeURIComponent(campaignId)}/results/${encodeURIComponent(attemptId)}/${encodeURIComponent(variantId)}/report.zip`,
  campaignAttempts: (id: string, refresh = false) =>
    request<{
      campaign_id: string;
      attempts: Array<Record<string, any>>;
      partial_errors: Array<Record<string, string>>;
    }>(
      `/api/campaigns/${encodeURIComponent(id)}/attempts${
        refresh ? "?refresh=true" : ""
      }`,
    ),
  campaignAttempt: (id: string, attemptId: string, refresh = false) =>
    request<{
      campaign_id: string;
      attempt: Record<string, any>;
      partial_errors: Array<Record<string, string>>;
    }>(
      `/api/campaigns/${encodeURIComponent(id)}/attempts/${encodeURIComponent(
        attemptId,
      )}${refresh ? "?refresh=true" : ""}`,
    ),
  queueMechanics: (id: string, attempt_id = "original") =>
    request<{ jobs: JobRecord[]; deduplicated?: boolean }>(
      `/api/campaigns/${encodeURIComponent(id)}/queue-mechanics`,
      { method: "POST", body: json({ attempt_id }) },
    ),
  queueRun: (id: string, attempt_id = "original") =>
    request<{ jobs: JobRecord[]; deduplicated?: boolean }>(
      `/api/campaigns/${encodeURIComponent(id)}/queue-run`,
      { method: "POST", body: json({ attempt_id }) },
    ),
  recoverFinalization: (id: string, attemptId: string) =>
    request<{
      recovered: boolean;
      source_job_id: string;
      research_verdict: string;
      finalization: Record<string, unknown>;
      next_action: string;
    }>(
      `/api/campaigns/${encodeURIComponent(id)}/attempts/${encodeURIComponent(attemptId)}/recover-finalization`,
      { method: "POST" },
    ),
  queueAccountAssessment: (id: string, value: Record<string, unknown>) =>
    request<{ job: JobRecord }>(
      `/api/campaigns/${encodeURIComponent(id)}/account-assessments`,
      { method: "POST", body: json(value) },
    ),
  nextVariant: (id: string) =>
    request<Record<string, any>>(
      `/api/campaigns/${encodeURIComponent(id)}/next-variant`,
    ),
  appendNextVariant: (id: string, value: unknown) =>
    request<Record<string, any>>(
      `/api/campaigns/${encodeURIComponent(id)}/next-variant`,
      { method: "POST", body: json(value) },
    ),
  reviews: () =>
    request<{
      items: ReviewTask[];
      mechanics: ReviewTask[];
      candidate: ReviewTask[];
    }>("/api/reviews"),
  mechanicsReview: (
    campaignId: string,
    attemptId: string,
    variantId: string,
    tradeId?: string,
  ) =>
    request<Record<string, any>>(
      `/api/reviews/mechanics/${encodeURIComponent(campaignId)}/${encodeURIComponent(attemptId)}/${encodeURIComponent(variantId)}${tradeId ? `?trade_id=${encodeURIComponent(tradeId)}` : ""}`,
    ),
  annotateMechanics: (value: unknown) =>
    request<Record<string, any>>("/api/reviews/mechanics/annotation", {
      method: "POST",
      body: json(value),
    }),
  decideMechanics: (value: unknown) =>
    request<Record<string, any>>("/api/reviews/mechanics/decision", {
      method: "POST",
      body: json(value),
    }),
  decideCandidate: (value: unknown) =>
    request<Record<string, any>>("/api/reviews/candidate/decision", {
      method: "POST",
      body: json(value),
    }),
  forwardIncubations: (campaignId?: string) =>
    request<{ items: Array<Record<string, any>> }>(
      `/api/forward-incubations${campaignId ? `?campaign_id=${encodeURIComponent(campaignId)}` : ""}`,
    ),
  uploadForwardIncubationEvidence: (file: File) =>
    request<{
      upload_token: string;
      filename: string;
      size_bytes: number;
      sha256: string;
      local_only: boolean;
      reconciliation: null | {
        schema: string;
        usable: boolean;
        columns: string[];
        row_count: number;
        trade_count_delta: number | null;
        net_pnl_delta: number | null;
        prop_rule_breach: boolean | null;
        forced_flatten_violation: boolean | null;
        warnings: string[];
        blockers: string[];
      };
    }>(
      `/api/forward-incubations/evidence/upload?filename=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        body: file,
        headers: { "Content-Type": "application/octet-stream" },
      },
    ),
  startForwardIncubation: (value: unknown) =>
    request<Record<string, any>>("/api/forward-incubations", {
      method: "POST",
      body: json(value),
    }),
  appendForwardObservation: (
    campaignId: string,
    variantId: string,
    attemptId: string,
    value: unknown,
  ) =>
    request<Record<string, any>>(
      `/api/forward-incubations/${encodeURIComponent(campaignId)}/${encodeURIComponent(variantId)}/${encodeURIComponent(attemptId)}/observations`,
      { method: "POST", body: json(value) },
    ),
  reviewForwardIncubation: (
    campaignId: string,
    variantId: string,
    attemptId: string,
    value: unknown,
  ) =>
    request<Record<string, any>>(
      `/api/forward-incubations/${encodeURIComponent(campaignId)}/${encodeURIComponent(variantId)}/${encodeURIComponent(attemptId)}/reviews`,
      { method: "POST", body: json(value) },
    ),
  retireForwardIncubation: (
    campaignId: string,
    variantId: string,
    attemptId: string,
    value: unknown,
  ) =>
    request<Record<string, any>>(
      `/api/forward-incubations/${encodeURIComponent(campaignId)}/${encodeURIComponent(variantId)}/${encodeURIComponent(attemptId)}/retire`,
      { method: "POST", body: json(value) },
    ),
  lifecycleCandidates: () =>
    request<{ items: Array<Record<string, any>> }>("/api/lifecycle/candidates"),
  portfolioReviews: () =>
    request<{ items: Array<Record<string, any>> }>("/api/portfolio-reviews"),
  portfolioReview: (reviewId: string) =>
    request<Record<string, any>>(
      `/api/portfolio-reviews/${encodeURIComponent(reviewId)}`,
    ),
  createPortfolioReview: (value: unknown) =>
    request<Record<string, any>>("/api/portfolio-reviews", {
      method: "POST",
      body: json(value),
    }),
  deploymentDecisions: () =>
    request<{ items: Array<Record<string, any>> }>("/api/deployment-decisions"),
  deploymentDecision: (decisionId: string) =>
    request<Record<string, any>>(
      `/api/deployment-decisions/${encodeURIComponent(decisionId)}`,
    ),
  createDeploymentDecision: (value: unknown) =>
    request<Record<string, any>>("/api/deployment-decisions", {
      method: "POST",
      body: json(value),
    }),
  uploadDeploymentMonitoringEvidence: (file: File) =>
    request<{
      upload_token: string;
      filename: string;
      size_bytes: number;
      sha256: string;
    }>(
      `/api/deployment-monitoring/evidence/upload?filename=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        body: file,
        headers: { "Content-Type": "application/octet-stream" },
      },
    ),
  deploymentMonitoring: (decisionId: string) =>
    request<Record<string, any>>(
      `/api/deployment-decisions/${encodeURIComponent(decisionId)}/monitoring`,
    ),
  appendDeploymentMonitoring: (
    decisionId: string,
    value: unknown,
  ) =>
    request<Record<string, any>>(
      `/api/deployment-decisions/${encodeURIComponent(decisionId)}/monitoring`,
      { method: "POST", body: json(value) },
    ),
  followUpOptions: (id: string, parentAttemptId = "original") =>
    request<Record<string, any>>(
      `/api/campaigns/${encodeURIComponent(id)}/follow-up-options?parent_attempt_id=${encodeURIComponent(parentAttemptId)}`,
    ),
  createFollowUp: (id: string, value: unknown) =>
    request<Record<string, any>>(
      `/api/campaigns/${encodeURIComponent(id)}/follow-ups`,
      { method: "POST", body: json(value) },
    ),
  libraries: () => request<LibrariesResponse>("/api/libraries"),
  queueStrategyCertification: (strategyId: string, requestId: string) =>
    request<{ job: JobRecord }>(
      `/api/strategies/${encodeURIComponent(strategyId)}/certify`,
      { method: "POST", body: json({ request_id: requestId }) },
    ),
  jobs: () => request<JobRecord[] | { jobs: JobRecord[] }>("/api/jobs"),
  cancelJob: (id: string) =>
    request<JobRecord>(`/api/jobs/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
    }),
  factoryStatus: (campaignId?: string) =>
    request<FactoryStatus>(
      `/api/factory/status${campaignId ? `?campaign_id=${encodeURIComponent(campaignId)}` : ""}`,
    ),
  factoryTasks: (limit = 20) =>
    request<CodexTaskRecord[] | { tasks: CodexTaskRecord[] }>(
      `/api/factory/tasks?limit=${encodeURIComponent(String(limit))}`,
    ),
  factoryTask: (id: string) =>
    request<CodexTaskRecord | { task: CodexTaskRecord }>(
      `/api/factory/tasks/${encodeURIComponent(id)}`,
    ),
  runNextFactoryStep: (value: {
    request_id: string;
    campaign_id?: string;
  }) =>
    request<
      CodexTaskRecord | { task: CodexTaskRecord; deduplicated?: boolean }
    >("/api/factory/run-next", {
      method: "POST",
      body: json(value),
    }),
  cancelFactoryTask: (id: string) =>
    request<CodexTaskRecord | { task: CodexTaskRecord }>(
      `/api/factory/tasks/${encodeURIComponent(id)}/cancel`,
      { method: "POST" },
    ),
  setFactoryProposalDisposition: (
    id: string,
    value: {
      disposition: "ACKNOWLEDGE" | "DISMISS";
      reviewer: string;
      notes: string;
    },
  ) =>
    request<CodexTaskRecord | { task: CodexTaskRecord }>(
      `/api/factory/tasks/${encodeURIComponent(id)}/proposal-disposition`,
      { method: "POST", body: json(value) },
    ),
  recordFactoryReviewedSource: (
    id: string,
    value: {
      reviewer: string;
      notes: string;
      verified_metadata_fields: string[];
      content_sha256: string;
      retraction_status: "NOT_RETRACTED" | "CORRECTED";
      verification_method: string;
      claim_reviews: Array<{
        claim_id: string;
        proposed_support: "DIRECT" | "CONFLICTING" | "INFERENCE";
        decision: "ACCEPT" | "REJECT";
        evidence_sha256?: string | null;
        verification_method: string;
        notes: string;
      }>;
    },
  ) =>
    request<Record<string, unknown>>(
      `/api/factory/tasks/${encodeURIComponent(id)}/reviewed-source-evidence`,
      { method: "POST", body: json(value) },
    ),
  recordFactoryReviewedHypothesis: (
    id: string,
    value: {
      reviewer: string;
      notes: string;
      reviewed_fields: string[];
      objective_alignment: "PASS";
      source_claim_alignment: "PASS";
      falsifiability: "PASS";
      information_timeline_no_lookahead: "PASS";
      execution_cost_awareness: "PASS";
    },
  ) =>
    request<Record<string, unknown>>(
      `/api/factory/tasks/${encodeURIComponent(id)}/reviewed-hypothesis`,
      { method: "POST", body: json(value) },
    ),
  recordFactoryReviewedEngineeringIntent: (
    id: string,
    value: {
      reviewer: string;
      notes: string;
      reviewed_fields: string[];
      hypothesis_alignment: "PASS";
      unsupported_scope_confirmed: "PASS";
      causal_timeline_reviewed: "PASS";
    },
  ) =>
    request<Record<string, unknown>>(
      `/api/factory/tasks/${encodeURIComponent(id)}/reviewed-engineering-intent`,
      { method: "POST", body: json(value) },
    ),
  setFactorySelectedAction: (
    id: string,
    value: {
      selected_action:
        | "ABANDON_EDGE"
        | "PROPOSE_SUCCESSOR"
        | "START_NEW_RESEARCH_GENERATION"
        | "STOP_NO_FRESH_HOLDOUT";
      reviewer: string;
      notes: string;
    },
  ) =>
    request<CodexTaskRecord | { task: CodexTaskRecord }>(
      `/api/factory/tasks/${encodeURIComponent(id)}/selected-action`,
      { method: "POST", body: json(value) },
    ),
  completeFactorySelectedAction: (
    id: string,
    value: { reviewer: string; notes: string },
  ) =>
    request<CodexTaskRecord | { task: CodexTaskRecord }>(
      `/api/factory/tasks/${encodeURIComponent(id)}/selected-action-completion`,
      { method: "POST", body: json(value) },
    ),
  pauseFactory: () =>
    request<FactoryStatus>("/api/factory/pause", { method: "POST" }),
  resumeFactory: () =>
    request<FactoryStatus>("/api/factory/resume", { method: "POST" }),
  repairDerivedViews: () =>
    request<Record<string, any>>("/api/workflow/repair-derived-views", {
      method: "POST",
    }),
  inspectUpload: (file: File) =>
    request<{
      upload_token: string;
      filename: string;
      size_bytes: number;
      columns: string[];
      suggested_mapping: Record<string, string | null>;
      discovery?: Record<string, any>;
    }>(`/api/uploads/inspect?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      body: file,
      headers: { "Content-Type": "application/octet-stream" },
    }),
  uploadMechanicsChart: (file: File) =>
    request<{ upload_token: string; filename: string; size_bytes: number }>(
      `/api/reviews/mechanics/reconciliation-upload?filename=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        body: file,
        headers: { "Content-Type": "text/csv" },
      },
    ),
  reconcileMechanicsChart: (value: unknown) =>
    request<Record<string, any>>("/api/reviews/mechanics/reconcile-chart", {
      method: "POST",
      body: json(value),
    }),
  importDataset: (value: unknown) =>
    request<Record<string, any>>("/api/datasets/import", {
      method: "POST",
      body: json(value),
    }),
  dataset: (datasetId: string) =>
    request<Record<string, any>>(
      `/api/datasets/${encodeURIComponent(datasetId)}`,
    ),
  compareDatasets: (leftId: string, rightId: string) =>
    request<Record<string, any>>(
      `/api/datasets/compare/${encodeURIComponent(leftId)}/${encodeURIComponent(rightId)}`,
    ),
  analysisCapabilities: () =>
    request<{
      scope: string;
      capabilities: Array<Record<string, string>>;
    }>("/api/analysis/capabilities"),
  analysisScanner: () =>
    request<{
      generated_at: string;
      rows: Array<Record<string, any>>;
      note: string;
    }>("/api/analysis/scanner"),
  analysisChart: (
    datasetId: string,
    options: {
      resolution?: string;
      chart_type?: string;
      limit?: number;
      compare_dataset_id?: string;
    } = {},
  ) => {
    const params = new URLSearchParams();
    if (options.resolution) params.set("resolution", options.resolution);
    if (options.chart_type) params.set("chart_type", options.chart_type);
    if (options.limit) params.set("limit", String(options.limit));
    if (options.compare_dataset_id)
      params.set("compare_dataset_id", options.compare_dataset_id);
    const query = params.toString();
    return request<Record<string, any>>(
      `/api/analysis/chart/${encodeURIComponent(datasetId)}${query ? `?${query}` : ""}`,
    );
  },
  sessionTemplates: () =>
    request<{ templates: Array<Record<string, any>>; note: string }>(
      "/api/data/session-templates",
    ),
  runTutorial: () =>
    request<Record<string, any>>("/api/tutorial/run", {
      method: "POST",
      body: json({ reset: true }),
    }),
  settings: () => request<StudioSettings>("/api/settings"),
  saveSettings: (settings: StudioSettings) =>
    request<StudioSettings | { settings: StudioSettings; saved: boolean }>(
      "/api/settings",
      { method: "PUT", body: json(settings) },
    ),
  aiStatus: () =>
    request<{
      configured: boolean;
      model?: string;
      retention_notice?: string;
      zero_data_retention_enabled?: boolean;
      privacy_boundary?: string;
    }>("/api/ai/status"),
  inspectResearchPdf: (file: File) =>
    request<{
      upload_token: string;
      filename: string;
      size_bytes: number;
      pages: Array<{
        index: number;
        page_number: number;
        characters: number;
        preview: string;
      }>;
      local_only: boolean;
    }>(`/api/ai/pdf/inspect?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      body: file,
      headers: { "Content-Type": "application/pdf" },
    }),
  extractResearchPdf: (upload_token: string, page_indexes: number[]) =>
    request<{
      selected_text: string;
      characters: number;
      page_indexes: number[];
      local_only: boolean;
    }>("/api/ai/pdf/extract", {
      method: "POST",
      body: json({ upload_token, page_indexes }),
    }),
  saveAiKey: (api_key: string) =>
    request<{ configured: boolean; stored_in?: string }>("/api/ai/key", {
      method: "PUT",
      body: json({ api_key }),
    }),
  removeAiKey: () =>
    request<{ configured: boolean }>("/api/ai/key", { method: "DELETE" }),
  suggestResearchBrief: (value: unknown) =>
    request<Record<string, any>>("/api/ai/suggest", {
      method: "POST",
      body: json(value),
    }),
};

export function normalizeBootstrap(
  raw: Partial<BootstrapResponse> | Record<string, any>,
): BootstrapResponse {
  const data = ((raw as Record<string, any>).data || raw) as Record<
    string,
    any
  >;
  return {
    workspace: data.workspace || data.project || {},
    drafts: array(data.drafts || data.live_drafts),
    campaigns: array(data.campaigns || data.published_campaigns),
    reviews: array(data.reviews || data.review_queue),
    jobs: array<Record<string, any>>(data.jobs || data.job_queue).map(
      (job) => ({
        ...job,
        state: job.state || job.operational_state || "NOT_QUEUED",
      }),
    ) as JobRecord[],
    libraries: data.libraries,
    settings: data.settings,
    counts: data.counts,
    attention: array(data.attention),
    indexed_attention: array(data.indexed_attention),
    workflow_actions: array(data.workflow_actions),
  };
}

export function unwrapArray<T>(
  raw: T[] | Record<string, T[]>,
  key: string,
): T[] {
  return Array.isArray(raw) ? raw : array(raw[key]);
}

function array<T>(value: unknown): T[] {
  return Array.isArray(value) ? value : [];
}
