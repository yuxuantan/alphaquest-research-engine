import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Icon } from "../components/Icons";
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
  useEffect(() => {
    if (selectedDataset) setQuery(selectedDataset);
  }, [selectedDataset]);
  useEffect(() => {
    api
      .libraries()
      .then(setData)
      .catch((reason) =>
        setError(
          reason instanceof Error ? reason.message : "Library unavailable",
        ),
      )
      .finally(() => setLoading(false));
  }, []);
  const isData = section === "data";
  const items = useMemo(
    () =>
      isData
        ? data.datasets.filter((item) =>
            `${item.dataset_id} ${item.symbol} ${item.timeframe}`
              .toLowerCase()
              .includes(query.toLowerCase()),
          )
        : data.modules.filter((item) =>
            `${item.name} ${item.module_type} ${item.summary}`
              .toLowerCase()
              .includes(query.toLowerCase()),
          ),
    [data, isData, query],
  );
  return (
    <div className="page">
      <PageHeader
        eyebrow="Certified resources"
        title={isData ? "Data library" : "Method library"}
        description={
          isData
            ? "Governed bars with disclosed lineage, timestamp meaning, validation, and quality verdict."
            : "Only certified modules are available to new no-code research; legacy modules remain developer-only."
        }
      />
      <label className="search-box library-search">
        <Icon name="search" />
        <span className="sr-only">Search library</span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Search ${isData ? "datasets" : "methods"}…`}
        />
      </label>
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
      )}{" "}
      {loading ? (
        <Skeleton lines={8} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={isData ? "database" : "methods"}
          title={`No ${isData ? "datasets" : "methods"} found`}
          body={
            query
              ? "Clear the search or use a broader term."
              : isData
                ? "Import local CSV or Parquet bars through governed intake."
                : "Certified module manifests will appear here."
          }
        />
      ) : isData ? (
        <DatasetGrid items={items as DatasetSummary[]} />
      ) : (
        <ModuleGrid items={items as ModuleSummary[]} />
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
          <h2>{humanize(item.dataset_id)}</h2>
          <p>
            {item.symbol} · {item.timeframe} ·{" "}
            {item.row_count?.toLocaleString() || "—"} rows
          </p>
          <dl className="compact-dl">
            <div>
              <dt>Timezone</dt>
              <dd>{item.timezone || "Not recorded"}</dd>
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
          <TechnicalDetails>
            <pre>{JSON.stringify(item, null, 2)}</pre>
          </TechnicalDetails>
        </Card>
      ))}
    </div>
  );
}

function ModuleGrid({ items }: { items: ModuleSummary[] }) {
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
              value={
                item.certification_status === "developer_only"
                  ? "Developer only"
                  : "Certified"
              }
            />
          </div>
          <span className="method-type">
            {labels[item.module_type || ""] || humanize(item.module_type)}
          </span>
          <h2>{humanize(item.name)}</h2>
          {item.strategy_package && (
            <p className="eyebrow">
              Certified strategy package · implementation v
              {item.implementation_version}
            </p>
          )}
          <p>
            {item.summary ||
              "Certified module with declared timing and typed parameters."}
          </p>
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
