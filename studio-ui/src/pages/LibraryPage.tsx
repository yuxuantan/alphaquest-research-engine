import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Icon } from "../components/Icons";
import {
  moduleAvailabilityLabel,
  strategyPackageLabel,
} from "../strategyAvailability";
import {
  Button,
  Card,
  EmptyState,
  Field,
  Notice,
  PageHeader,
  Skeleton,
  StatusBadge,
  TechnicalDetails,
  formatMarketDate,
  humanize,
} from "../components/UI";
import type {
  DatasetSummary,
  LibrariesResponse,
  ModuleSummary,
} from "../types";

export function LibraryPage() {
  const { section = "data" } = useParams();
  const [searchParams] = useSearchParams();
  const selectedDataset = searchParams.get("dataset") || "";
  const [data, setData] = useState<LibrariesResponse>({
    datasets: [],
    modules: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState(selectedDataset);
  const [quality, setQuality] = useState("all");
  const [resourceType, setResourceType] = useState("all");
  const [certification, setCertification] = useState("all");
  const refreshLibraries = () =>
    api
      .libraries()
      .then(setData)
      .catch((reason) =>
        setError(reason instanceof Error ? reason.message : "Library unavailable"),
      );
  useEffect(() => {
    if (selectedDataset) setQuery(selectedDataset);
  }, [selectedDataset]);
  useEffect(() => {
    refreshLibraries().finally(() => setLoading(false));
  }, []);
  const isData = section === "data";
  const isAccounts = section === "accounts";
  const items = useMemo(
    () =>
      isData
        ? data.datasets.filter(
            (item) =>
              `${item.display_name} ${item.dataset_id} ${item.symbol} ${item.timeframe} ${item.source_type} ${(item.capabilities || []).join(" ")}`
                .toLowerCase()
                .includes(query.toLowerCase()) &&
              (quality === "all" ||
                String(item.quality_verdict).toLowerCase() === quality) &&
              (resourceType === "all" ||
                String(item.source_type || "unknown") === resourceType),
          )
        : isAccounts
          ? (data.account_profiles || []).filter(
              (item) =>
                `${item.name} ${item.profile_id} ${item.provider} ${item.program} ${item.account_kind}`
                  .toLowerCase()
                  .includes(query.toLowerCase()) &&
                (resourceType === "all" || item.account_kind === resourceType),
            )
          : data.modules.filter(
            (item) =>
              `${item.name} ${item.module_type} ${item.summary}`
                .toLowerCase()
                .includes(query.toLowerCase()) &&
              (resourceType === "all" ||
                (resourceType === "package"
                  ? item.strategy_package
                  : item.module_type === resourceType)) &&
              (certification === "all" ||
                (certification === "certified"
                  ? item.certification_status !== "developer_only"
                  : item.certification_status === "developer_only")),
          ),
    [data, isData, isAccounts, query, quality, resourceType, certification],
  );
  const sourceTypes = [
    ...new Set(
      data.datasets.map((item: any) => String(item.source_type || "unknown")),
    ),
  ];
  return (
    <div className="page">
      <PageHeader
        eyebrow="Certified resources"
        title={
          isData ? "Data library" : isAccounts ? "Account rule profiles" : "Method library"
        }
        description={
          isData
            ? "Governed bars with disclosed lineage, timestamp meaning, validation, and quality verdict."
            : isAccounts
              ? "Versioned challenge, funded, and live-account rules used for destination-specific suitability tests."
            : "Only certified modules are available to new no-code research; legacy modules remain developer-only."
        }
      />
      <label className="search-box library-search">
        <Icon name="search" />
        <span className="sr-only">Search library</span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Search ${isData ? "datasets" : isAccounts ? "account profiles" : "methods"}…`}
        />
      </label>
      <div className="library-filters" aria-label="Library filters">
        {isData && (
          <label>
            <span>Quality</span>
            <select value={quality} onChange={(e) => setQuality(e.target.value)}>
              <option value="all">All verdicts</option>
              <option value="pass">PASS only</option>
              <option value="needs manual review">Needs manual review</option>
            </select>
          </label>
        )}
        <label>
          <span>{isData ? "Source" : isAccounts ? "Account phase" : "Method role"}</span>
          <select
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
          >
            <option value="all">All {isData ? "sources" : "roles"}</option>
            {isData ? (
              sourceTypes.map((source) => (
                <option key={source} value={source}>
                  {humanize(source)}
                </option>
              ))
            ) : isAccounts ? (
              <>
                <option value="prop_challenge">Prop challenge</option>
                <option value="prop_funded">Prop funded</option>
                <option value="live">Live account</option>
              </>
            ) : (
              <>
                <option value="entry">Entry</option>
                <option value="sl">Stop loss</option>
                <option value="tp">Target / exit</option>
                <option value="package">Strategy package</option>
              </>
            )}
          </select>
        </label>
        {!isData && !isAccounts && (
          <label>
            <span>Availability</span>
            <select
              value={certification}
              onChange={(e) => setCertification(e.target.value)}
            >
              <option value="all">All availability</option>
              <option value="certified">Certified for Studio</option>
              <option value="developer_only">Developer only</option>
            </select>
          </label>
        )}
        <span>{items.length} matching resources</span>
      </div>
      {error && <Notice tone="danger">{error}</Notice>}
      {isData && (
        <DataImporter
          onImported={(manifest) =>
            setData((old) => ({
              ...old,
              datasets: [manifest, ...old.datasets],
            }))
          }
        />
      )}
      {!isData && !isAccounts && (data.execution_profiles || []).length > 0 && (
        <ExecutionProfileCatalog profiles={data.execution_profiles || []} />
      )}{" "}
      {loading ? (
        <Skeleton lines={8} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={isData ? "database" : isAccounts ? "shield" : "methods"}
          title={`No ${isData ? "datasets" : isAccounts ? "account profiles" : "methods"} found`}
          body={
            query
              ? "Clear the search or use a broader term."
              : isData
                ? "Import local CSV or Parquet bars through governed intake."
                : isAccounts
                  ? "Reviewed account profiles will appear here."
                  : "Certified module manifests will appear here."
          }
        />
      ) : isData ? (
        <DatasetGrid items={items as DatasetSummary[]} />
      ) : isAccounts ? (
        <AccountProfileGrid items={items as Array<Record<string, any>>} />
      ) : (
        <ModuleGrid
          items={items as ModuleSummary[]}
          onCertificationQueued={refreshLibraries}
        />
      )}
    </div>
  );
}

function DataImporter({
  onImported,
}: {
  onImported: (manifest: DatasetSummary) => void;
}) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [inspection, setInspection] = useState<any>(null);
  const [rollFile, setRollFile] = useState<File | null>(null);
  const [rollInspection, setRollInspection] = useState<any>(null);
  const [sessionTemplates, setSessionTemplates] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState<any>({
    dataset_id: "",
    symbol: "ES",
    timeframe: "1m",
    timezone: "America/New_York",
    timestamp_semantics: "bar_open",
    roll_policy: "single_contract",
    single_contract_confirmed: false,
  });
  useEffect(() => {
    api
      .sessionTemplates()
      .then((value) => setSessionTemplates(value.templates || []))
      .catch(() => setSessionTemplates([]));
  }, []);
  async function inspect() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const value = await api.inspectUpload(file);
      setInspection(value);
      setForm((old: any) => ({
        ...old,
        dataset_id: file.name
          .replace(/\.[^.]+$/, "")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "_")
          .replace(/^_|_$/g, ""),
        ...Object.fromEntries(
          Object.entries(value.suggested_mapping).map(([key, val]) => [
            `${key}_column`,
            val,
          ]),
        ),
      }));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "File inspection failed",
      );
    } finally {
      setBusy(false);
    }
  }
  async function importFile(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.importDataset({
        upload_token: inspection.upload_token,
        spec: {
          ...form,
          exchange_timezone: "America/New_York",
          contract_column:
            form.roll_policy === "explicit_roll_calendar"
              ? form.contract_column
              : null,
        },
        roll_calendar_upload_token:
          form.roll_policy === "explicit_roll_calendar"
            ? rollInspection?.upload_token
            : null,
      });
      onImported(result.manifest);
      setOpen(false);
      setFile(null);
      setInspection(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Import stopped");
    } finally {
      setBusy(false);
    }
  }
  async function inspectRollCalendar() {
    if (!rollFile) return;
    setBusy(true);
    setError("");
    try {
      setRollInspection(await api.inspectUpload(rollFile));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Roll-calendar inspection failed",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="import-panel">
      <button className="import-trigger" onClick={() => setOpen(!open)}>
        <span>
          <Icon name="plus" />
        </span>
        <span>
          <strong>Import local market data</strong>
          <small>CSV or Parquet · original quarantined before validation</small>
        </span>
        <Icon name={open ? "close" : "chevron"} />
      </button>
      {open && (
        <Card className="import-workflow">
          {error && (
            <Notice tone="danger" title="Import stopped">
              {error}
            </Notice>
          )}
          {!inspection ? (
            <div className="upload-step">
              <label className="drop-zone">
                <input
                  type="file"
                  accept=".csv,.parquet,.pq"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
                <Icon name="data" />
                <strong>
                  {file ? file.name : "Choose CSV or Parquet bars"}
                </strong>
                <small>
                  {file
                    ? `${(file.size / 1024 / 1024).toFixed(2)} MB selected`
                    : "Your original file is copied to quarantine before parsing."}
                </small>
              </label>
              <Button onClick={() => void inspect()} disabled={!file || busy}>
                {busy ? "Inspecting…" : "Inspect columns"}
              </Button>
            </div>
          ) : (
            <form onSubmit={importFile}>
              <div className="import-phase">
                <span>
                  <Icon name="check" />
                </span>
                <div>
                  <strong>{inspection.filename}</strong>
                  <small>
                    {inspection.columns.length} columns found · source retained
                    in quarantine
                  </small>
                  {inspection.discovery && (
                    <small>
                      {inspection.discovery.sample_rows} rows sampled ·{" "}
                      {inspection.discovery.contract_candidates?.length || 0}{" "}
                      contract field candidate(s) ·{" "}
                      {inspection.discovery.timestamp_candidates?.length || 0}{" "}
                      timestamp field candidate(s)
                    </small>
                  )}
                </div>
                <button type="button" onClick={() => setInspection(null)}>
                  Choose another
                </button>
              </div>
              <div className="form-grid three">
                <Field label="Dataset name">
                  <input
                    value={form.dataset_id}
                    onChange={(e) =>
                      setForm({ ...form, dataset_id: e.target.value })
                    }
                    required
                  />
                </Field>
                <Field label="Market">
                  <select
                    value={form.symbol}
                    onChange={(e) =>
                      setForm({ ...form, symbol: e.target.value })
                    }
                  >
                    <option>ES</option>
                    <option>NQ</option>
                  </select>
                </Field>
                <Field label="Timeframe">
                  <select
                    value={form.timeframe}
                    onChange={(e) =>
                      setForm({ ...form, timeframe: e.target.value })
                    }
                  >
                    <option>1m</option>
                    <option>5m</option>
                    <option>15m</option>
                  </select>
                </Field>
                <Field label="Source timezone">
                  <input
                    value={form.timezone}
                    onChange={(e) =>
                      setForm({ ...form, timezone: e.target.value })
                    }
                  />
                </Field>
                <Field label="Certified session reference">
                  <select
                    value={form.session_template_id || ""}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        session_template_id: event.target.value,
                      })
                    }
                  >
                    <option value="">No reference selected</option>
                    {sessionTemplates.map((template) => (
                      <option
                        key={template.template_id}
                        value={template.template_id}
                      >
                        {template.label} · {template.session_start}–
                        {template.session_end}
                      </option>
                    ))}
                  </select>
                  <small>
                    Reference only; campaign session controls remain frozen
                    separately.
                  </small>
                </Field>
                <Field label="Timestamp means">
                  <select
                    value={form.timestamp_semantics}
                    onChange={(e) =>
                      setForm({ ...form, timestamp_semantics: e.target.value })
                    }
                  >
                    <option value="bar_open">Start of bar</option>
                    <option value="bar_close">End of bar</option>
                  </select>
                </Field>
                <Field label="Contract lineage">
                  <select
                    value={form.roll_policy}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        roll_policy: e.target.value,
                        single_contract_confirmed:
                          e.target.value === "single_contract"
                            ? form.single_contract_confirmed
                            : false,
                      })
                    }
                  >
                    <option value="single_contract">
                      One outright contract
                    </option>
                    <option value="explicit_roll_calendar">
                      Explicit roll calendar
                    </option>
                  </select>
                </Field>
              </div>
              <h3>Column mapping</h3>
              <div className="mapping-grid">
                {["timestamp", "open", "high", "low", "close", "volume"].map(
                  (name) => (
                    <Field label={humanize(name)} key={name}>
                      <select
                        value={form[`${name}_column`] || ""}
                        onChange={(e) =>
                          setForm({
                            ...form,
                            [`${name}_column`]: e.target.value,
                          })
                        }
                      >
                        {inspection.columns.map((column: string) => (
                          <option key={column}>{column}</option>
                        ))}
                      </select>
                    </Field>
                  ),
                )}
              </div>
              {form.roll_policy === "single_contract" && (
                <label className="confirmation compact">
                  <input
                    type="checkbox"
                    checked={form.single_contract_confirmed}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        single_contract_confirmed: e.target.checked,
                      })
                    }
                  />
                  <span>
                    <Icon name="check" />
                  </span>
                  <div>
                    <strong>
                      This file contains exactly one futures contract
                    </strong>
                    <small>
                      Continuous or stitched files require explicit causal roll
                      lineage.
                    </small>
                  </div>
                </label>
              )}
              {form.roll_policy === "explicit_roll_calendar" && (
                <div className="roll-calendar-panel">
                  <Notice tone="warning" title="Causal roll lineage required">
                    Select the contract symbol carried on every bar, then attach
                    a CSV with start_timestamp and contract_symbol.
                  </Notice>
                  <Field label="Contract column in market data">
                    <select
                      value={form.contract_column || ""}
                      onChange={(e) =>
                        setForm({ ...form, contract_column: e.target.value })
                      }
                      required
                    >
                      <option value="">Choose contract column…</option>
                      {inspection.columns.map((column: string) => (
                        <option key={column}>{column}</option>
                      ))}
                    </select>
                  </Field>
                  <div className="roll-upload-row">
                    <label className="field">
                      <span className="field-label">Roll calendar CSV</span>
                      <input
                        type="file"
                        accept=".csv"
                        onChange={(e) => {
                          setRollFile(e.target.files?.[0] || null);
                          setRollInspection(null);
                        }}
                      />
                    </label>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={!rollFile || busy}
                      onClick={() => void inspectRollCalendar()}
                    >
                      {rollInspection
                        ? "Calendar inspected"
                        : "Inspect calendar"}
                    </Button>
                  </div>
                  {rollInspection && (
                    <Notice tone="success">
                      {rollInspection.filename} retained in quarantine ·
                      columns: {rollInspection.columns.join(", ")}
                    </Notice>
                  )}
                </div>
              )}
              <div className="form-footer">
                <Button
                  variant="secondary"
                  type="button"
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={
                    busy ||
                    (form.roll_policy === "single_contract" &&
                      !form.single_contract_confirmed) ||
                    (form.roll_policy === "explicit_roll_calendar" &&
                      (!form.contract_column || !rollInspection))
                  }
                >
                  {busy ? "Validating…" : "Quarantine, validate, and import"}
                </Button>
              </div>
            </form>
          )}
        </Card>
      )}
    </section>
  );
}

function DatasetGrid({ items }: { items: DatasetSummary[] }) {
  const [expanded, setExpanded] = useState("");
  const [detail, setDetail] = useState<Record<string, any>>({});
  const [compareWith, setCompareWith] = useState<Record<string, string>>({});
  const [comparison, setComparison] = useState<Record<string, any>>({});
  async function toggle(datasetId: string) {
    if (expanded === datasetId) {
      setExpanded("");
      return;
    }
    setExpanded(datasetId);
    if (!detail[datasetId]) {
      setDetail((current) => ({
        ...current,
        [datasetId]: { loading: true },
      }));
      try {
        const value = await api.dataset(datasetId);
        setDetail((current) => ({ ...current, [datasetId]: value }));
      } catch (reason) {
        setDetail((current) => ({
          ...current,
          [datasetId]: {
            error:
              reason instanceof Error
                ? reason.message
                : "Dataset detail is unavailable",
          },
        }));
      }
    }
  }
  async function compare(datasetId: string) {
    const other = compareWith[datasetId];
    if (!other) return;
    const value = await api.compareDatasets(datasetId, other);
    setComparison((current) => ({ ...current, [datasetId]: value }));
  }
  return (
    <div className="library-grid">
      {items.map((item) => (
        <Card className="library-card" key={item.dataset_id}>
          <div className="library-card-head">
            <span>
              <Icon name="database" />
            </span>
            <StatusBadge
              value={item.quality_verdict || "Unknown"}
              kind="scientific"
            />
          </div>
          <h2>{item.display_name || humanize(item.dataset_id)}</h2>
          <p>
            {item.symbol} · {item.timeframe} ·{" "}
            {item.row_count?.toLocaleString() || "—"} rows
          </p>
          <code className="resource-id">{item.dataset_id}</code>
          <dl className="compact-dl">
            <div>
              <dt>Coverage</dt>
              <dd>
                {formatMarketDate(item.coverage_start)} →{" "}
                {formatMarketDate(item.coverage_end)}
              </dd>
            </div>
            <div>
              <dt>Market source</dt>
              <dd>{humanize(String(item.source_type || "Not recorded"))}</dd>
            </div>
            <div>
              <dt>Storage format</dt>
              <dd>{humanize(item.storage_format || "Not recorded")}</dd>
            </div>
            <div>
              <dt>Session timezone</dt>
              <dd>
                {item.exchange_timezone || item.timezone || "Not recorded"}
              </dd>
            </div>
            <div>
              <dt>Timestamp</dt>
              <dd>{humanize(item.timestamp_semantics)}</dd>
            </div>
            <div>
              <dt>Roll policy</dt>
              <dd>{humanize(item.roll_policy)}</dd>
            </div>
          </dl>
          <div className="dataset-defects">
            <span>{item.dropped_row_count || 0} dropped</span>
            <span>{item.gap_count || 0} gaps</span>
            <span>{item.duplicate_count || 0} duplicates</span>
            <span>{item.invalid_ohlc_count || 0} invalid OHLC</span>
          </div>
          {item.research_readiness && (
            <Notice
              tone={item.research_readiness.status === "READY" ? "success" : "warning"}
              title={`Research-window forecast: ${humanize(item.research_readiness.status)}`}
            >
              {item.research_readiness.available_months ?? "Unknown"} months available; approximately{" "}
              {item.research_readiness.required_months} required by the current sequential WFA and holdout policy.
            </Notice>
          )}
          {(item.capabilities || []).length > 0 && (
            <div className="capability-list" aria-label="Dataset capabilities">
              {item.capabilities?.map((capability) => (
                <span key={capability}>{humanize(capability)}</span>
              ))}
            </div>
          )}
          {item.quality_verdict === "NEEDS MANUAL REVIEW" &&
            (item.quality_notes || []).length > 0 && (
              <Notice tone="warning" title="Why review is required">
                {item.quality_notes?.slice(0, 2).join(" ")}
              </Notice>
            )}
          {(item.used_by || []).length > 0 && (
            <div className="resource-usage">
              <strong>
                Used by {item.used_by?.length} campaign
                {item.used_by?.length === 1 ? "" : "s"}
              </strong>
              {item.used_by?.slice(0, 3).map((usage) => (
                <Link
                  key={`${usage.campaign_id}-${usage.variant_id}`}
                  to={`/research/${usage.campaign_id}/mechanics?variant=${usage.variant_id}`}
                >
                  {usage.campaign_title} · {usage.variant_id}
                </Link>
              ))}
              {(item.used_by?.length || 0) > 3 && (
                <details>
                  <summary>
                    Show {(item.used_by?.length || 0) - 3} more campaigns
                  </summary>
                  <div>
                    {item.used_by?.slice(3).map((usage) => (
                      <Link
                        key={`${usage.campaign_id}-${usage.variant_id}`}
                        to={`/research/${usage.campaign_id}/mechanics?variant=${usage.variant_id}`}
                      >
                        {usage.campaign_title} · {usage.variant_id}
                      </Link>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}
          <div className="library-card-actions">
            <Button
              type="button"
              variant="secondary"
              onClick={() => void toggle(item.dataset_id)}
            >
              {expanded === item.dataset_id
                ? "Close data manager"
                : "Inspect dataset"}
            </Button>
          </div>
          {expanded === item.dataset_id && (
            <section className="dataset-manager">
              {!detail[item.dataset_id] ||
              detail[item.dataset_id].loading ? (
                <Skeleton lines={4} />
              ) : detail[item.dataset_id].error ? (
                <Notice tone="danger" title="Dataset detail unavailable">
                  {detail[item.dataset_id].error}
                </Notice>
              ) : (
                <>
                  <h3>Governed data-source manager</h3>
                  <dl className="compact-dl">
                    <div>
                      <dt>Manifest hash</dt>
                      <dd className="hash-value">
                        {detail[item.dataset_id].manifest_sha256}
                      </dd>
                    </div>
                    <div>
                      <dt>Contracts discovered</dt>
                      <dd>
                        {detail[item.dataset_id].contracts?.count ?? "—"} ·{" "}
                        {humanize(
                          detail[item.dataset_id].contracts?.continuous_contract ||
                            "none",
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Coverage gaps</dt>
                      <dd>
                        {detail[item.dataset_id].quality?.defects?.gap_count ?? 0}
                      </dd>
                    </div>
                    <div>
                      <dt>Cadence violations</dt>
                      <dd>
                        {detail[item.dataset_id].quality?.defects
                          ?.cadence_violation_count ?? 0}
                      </dd>
                    </div>
                  </dl>
                  <div className="roll-preview">
                    <strong>Roll calendar</strong>
                    {detail[item.dataset_id].roll_calendar?.available ? (
                      <ResultLikeTable
                        rows={
                          detail[item.dataset_id].roll_calendar.preview_rows || []
                        }
                      />
                    ) : (
                      <Notice tone="info">
                        {detail[item.dataset_id].roll_calendar?.reason}
                      </Notice>
                    )}
                  </div>
                  <div className="dataset-compare">
                    <Field label="Compare governed source">
                      <select
                        value={compareWith[item.dataset_id] || ""}
                        onChange={(event) =>
                          setCompareWith((current) => ({
                            ...current,
                            [item.dataset_id]: event.target.value,
                          }))
                        }
                      >
                        <option value="">Select another dataset</option>
                        {items
                          .filter(
                            (candidate) =>
                              candidate.dataset_id !== item.dataset_id,
                          )
                          .map((candidate) => (
                            <option
                              key={candidate.dataset_id}
                              value={candidate.dataset_id}
                            >
                              {candidate.display_name || candidate.dataset_id}
                            </option>
                          ))}
                      </select>
                    </Field>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={!compareWith[item.dataset_id]}
                      onClick={() => void compare(item.dataset_id)}
                    >
                      Compare manifests
                    </Button>
                  </div>
                  {comparison[item.dataset_id] && (
                    <div>
                      <Notice
                        tone={
                          comparison[item.dataset_id].comparable
                            ? "info"
                            : "warning"
                        }
                        title={
                          comparison[item.dataset_id].comparable
                            ? "Comparable symbol and timeframe"
                            : "Not directly comparable"
                        }
                      >
                        {comparison[item.dataset_id].warning}
                      </Notice>
                      <ResultLikeTable
                        rows={Object.entries(
                          comparison[item.dataset_id].comparison || {},
                        ).map(([metric, values]: [string, any]) => ({
                          metric: humanize(metric),
                          left: values.left,
                          right: values.right,
                          matches: values.matches,
                        }))}
                      />
                    </div>
                  )}
                </>
              )}
            </section>
          )}
          <TechnicalDetails>
            <pre>{JSON.stringify(item, null, 2)}</pre>
          </TechnicalDetails>
        </Card>
      ))}
    </div>
  );
}

function ResultLikeTable({ rows }: { rows: Array<Record<string, any>> }) {
  if (!rows.length) return <p>No rows retained.</p>;
  const columns = Object.keys(rows[0]);
  return (
    <div className="result-preview-table">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{humanize(column)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 200).map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{String(row[column] ?? "—")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExecutionProfileCatalog({
  profiles,
}: {
  profiles: Array<Record<string, any>>;
}) {
  return (
    <section className="execution-profile-catalog">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Execution certification</p>
          <h2>Generic order simulation profiles</h2>
          <p>
            A profile is selectable only while its implementation hash and
            required test categories match its manifest.
          </p>
        </div>
      </div>
      <div className="library-grid">
        {profiles.map((profile) => (
          <Card className="library-card" key={String(profile.profile_id)}>
            <div className="library-card-head">
              <span>
                <Icon name="shield" />
              </span>
              <StatusBadge
                value={
                  profile.status === "certified" ? "Certified" : "Unavailable"
                }
              />
            </div>
            <h2>{humanize(profile.profile_id)}</h2>
            <p>{profile.summary}</p>
            <div className="capability-list">
              {[
                "market",
                "limit",
                "stop",
                "stop limit",
                "OCO",
                "partial fills",
                "bid ask replay",
              ].map((name) => (
                <span key={name}>{name}</span>
              ))}
            </div>
            {(profile.excluded_capabilities || []).length > 0 && (
              <Notice tone="warning" title="Intentionally excluded">
                {profile.excluded_capabilities.join(" · ")}
              </Notice>
            )}
            {(profile.errors || []).length > 0 && (
              <Notice tone="danger">{profile.errors.join(" · ")}</Notice>
            )}
          </Card>
        ))}
      </div>
    </section>
  );
}

function AccountProfileGrid({
  items,
}: {
  items: Array<Record<string, any>>;
}) {
  return (
    <div className="library-grid account-profile-grid">
      {items.map((item) => {
        const rules = item.rules || {};
        const drawdown = rules.eod_drawdown || {};
        const policy = item.evaluation_policy || {};
        const provenance = item.provenance || {};
        return (
          <Card className="library-card account-profile-card" key={`${item.profile_id}@${item.version}`}>
            <div className="library-card-head">
              <span><Icon name="shield" /></span>
              <StatusBadge value={item.verification_status || "NEEDS MANUAL REVIEW"} />
            </div>
            <p className="eyebrow">{humanize(item.account_kind)} · version {item.version}</p>
            <h2>{item.name}</h2>
            <p>{item.description}</p>
            <dl className="definition-list compact">
              <div><dt>Provider</dt><dd>{item.provider}</dd></div>
              <div><dt>Nominal balance</dt><dd>{Number(item.nominal_balance || 0).toLocaleString(undefined, { style: "currency", currency: item.identity?.currency || "USD" })}</dd></div>
              <div><dt>EOD drawdown</dt><dd>{drawdown.amount ? Number(drawdown.amount).toLocaleString(undefined, { style: "currency", currency: item.identity?.currency || "USD" }) : "Not configured"}</dd></div>
              <div><dt>Close deadline</dt><dd>{rules.position_close_deadline || "Not declared"}</dd></div>
              <div><dt>Monte Carlo</dt><dd>{Number(policy.monte_carlo_runs || 0).toLocaleString()} paths</dd></div>
              <div><dt>Profile identity</dt><dd><code>{String(item.profile_sha256 || "").slice(0, 16)}</code></dd></div>
            </dl>
            <div className="capability-list">
              {(rules.permitted_instruments || []).map((instrument: string) => (
                <span key={instrument}>{instrument}</span>
              ))}
              <span>{rules.overnight_positions_allowed ? "Overnight allowed" : "Intraday only"}</span>
              <span>{item.promotable ? "Promotable" : "Inspection only"}</span>
            </div>
            <TechnicalDetails>
              <div className="account-contract-sections">
                <section>
                  <h3>Drawdown, sizing, and daily limits</h3>
                  <pre>{JSON.stringify({
                    eod_drawdown: rules.eod_drawdown,
                    fixed_maximum_contracts: rules.fixed_maximum_contracts,
                    fixed_daily_loss_limit: rules.fixed_daily_loss_limit,
                    scaling_tiers: rules.scaling_tiers,
                  }, null, 2)}</pre>
                </section>
                <section>
                  <h3>Challenge, payouts, and inactivity</h3>
                  <pre>{JSON.stringify({
                    evaluation: rules.evaluation,
                    payouts: rules.payouts,
                    inactivity: rules.inactivity,
                    acquisition: rules.acquisition,
                    manual_attestations_required: rules.manual_attestations_required,
                  }, null, 2)}</pre>
                </section>
                <section>
                  <h3>Suitability gates</h3>
                  <pre>{JSON.stringify(policy, null, 2)}</pre>
                </section>
                <section>
                  <h3>Official-source provenance</h3>
                  {(provenance.official_sources || []).map((source: any) => (
                    <p key={source.url}>
                      <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>{" "}
                      <small>accessed {source.accessed_at}</small>
                    </p>
                  ))}
                </section>
              </div>
            </TechnicalDetails>
          </Card>
        );
      })}
    </div>
  );
}

function ModuleGrid({
  items,
  onCertificationQueued,
}: {
  items: ModuleSummary[];
  onCertificationQueued: () => Promise<void>;
}) {
  const [certifying, setCertifying] = useState("");
  const [certificationFeedback, setCertificationFeedback] = useState<Record<string, string>>({});
  async function certify(item: ModuleSummary) {
    setCertifying(item.name);
    setCertificationFeedback((current) => ({ ...current, [item.name]: "" }));
    try {
      const requestId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${item.name}`;
      const result = await api.queueStrategyCertification(item.name, requestId);
      setCertificationFeedback((current) => ({
        ...current,
        [item.name]: `Certification job ${result.job.job_id.slice(0, 8)} queued. Follow it in Jobs; after it passes, create a certification-refresh attempt from the campaign.`,
      }));
      await onCertificationQueued();
    } catch (error) {
      setCertificationFeedback((current) => ({
        ...current,
        [item.name]: error instanceof Error ? error.message : "Certification job was not queued",
      }));
    } finally {
      setCertifying("");
    }
  }
  const labels: Record<string, string> = {
    entry: "Entry",
    sl: "Stop loss",
    tp: "Target / exit",
  };
  return (
    <div className="library-grid methods-grid">
      {items.map((item) => (
        <Card
          className="library-card method-card"
          key={`${item.module_type}-${item.name}`}
        >
          <div className="library-card-head">
            <span>
              <Icon name="methods" />
            </span>
            <StatusBadge
              value={moduleAvailabilityLabel(item)}
            />
          </div>
          <span className="method-type">
            {labels[item.module_type || ""] || humanize(item.module_type)}
          </span>
          <h2>{strategyPackageLabel(item) || humanize(item.name)}</h2>
          {item.strategy_package && (
            <p className="eyebrow">
              {item.available_for_publication === true
                ? "Certified strategy package"
                : "Unavailable for publication"}{" "}
              · implementation v
              {item.implementation_version}
            </p>
          )}
          <p>
            {item.strategy_description ||
              item.summary ||
              "Certified module with declared timing and typed parameters."}
          </p>
          {item.strategy_package && item.available_for_publication !== true && (
            <p>
              Historical inspection remains available, but this package cannot
              be selected for new publication.
              {(item.certification_errors || []).length > 0 && (
                <> {item.certification_errors?.join(" ")}</>
              )}
            </p>
          )}
          {item.strategy_package &&
            item.active_strategy_package === true &&
            item.certification_current === false && (
              <div className="resource-actions">
                <Button
                  disabled={certifying === item.name}
                  onClick={() => void certify(item)}
                >
                  {certifying === item.name
                    ? "Running declared certification…"
                    : "Run required tests and recertify"}
                </Button>
                <Notice tone="warning">
                  This certifies tested source bytes only. Existing attempts stay immutable and still require a certification-refresh attempt plus fresh mechanics review.
                </Notice>
              </div>
            )}
          {certificationFeedback[item.name] && (
            <Notice tone={certificationFeedback[item.name].includes("queued") ? "success" : "danger"}>
              {certificationFeedback[item.name]}
            </Notice>
          )}
          <div className="method-facts">
            <span>
              <Icon name="clock" />
              {humanize(item.decision_timing)}
            </span>
            <span>
              <Icon name="arrow" />
              {item.next_bar_entry
                ? "Next-bar entry"
                : "Declared execution timing"}
            </span>
          </div>
          {(item.used_by || []).length > 0 && (
            <div className="resource-usage">
              <strong>Used by</strong>
              {item.used_by?.map((usage) => (
                <Link
                  key={`${usage.campaign_id}-${usage.variant_id}`}
                  to={`/research/${usage.campaign_id}/mechanics?variant=${usage.variant_id}`}
                >
                  {usage.campaign_title} · {usage.variant_id}
                </Link>
              ))}
            </div>
          )}
          {item.parameters && (
            <TechnicalDetails>
              <div className="parameter-list">
                {Object.entries(item.parameters).map(
                  ([name, spec]: [string, any]) => (
                    <div key={name}>
                      <strong>{humanize(name)}</strong>
                      <span>
                        {spec.description || humanize(spec.value_type)}
                      </span>
                    </div>
                  ),
                )}
              </div>
            </TechnicalDetails>
          )}
        </Card>
      ))}
    </div>
  );
}
