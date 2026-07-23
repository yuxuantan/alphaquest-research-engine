import type {
  BootstrapResponse,
  CampaignDetail,
  DraftView,
  DuplicateReview,
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
  campaign: (id: string) =>
    request<{
      campaign: CampaignDetail;
      attempts: Array<Record<string, any>>;
      stage_matrix: Array<Record<string, any>>;
      latest_results: Record<string, any>;
      recommended_action: string;
    }>(`/api/campaigns/${encodeURIComponent(id)}`),
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
  jobs: () => request<JobRecord[] | { jobs: JobRecord[] }>("/api/jobs"),
  cancelJob: (id: string) =>
    request<JobRecord>(`/api/jobs/${encodeURIComponent(id)}/cancel`, {
      method: "POST",
    }),
  inspectUpload: (file: File) =>
    request<{
      upload_token: string;
      filename: string;
      size_bytes: number;
      columns: string[];
      suggested_mapping: Record<string, string | null>;
    }>(`/api/uploads/inspect?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      body: file,
      headers: { "Content-Type": "application/octet-stream" },
    }),
  importDataset: (value: unknown) =>
    request<Record<string, any>>("/api/datasets/import", {
      method: "POST",
      body: json(value),
    }),
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
