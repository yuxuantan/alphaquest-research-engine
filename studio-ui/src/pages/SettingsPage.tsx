import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import {
  Button,
  Card,
  Field,
  Notice,
  PageHeader,
  StatusBadge,
} from "../components/UI";
import type { FactoryStatus, StudioSettings } from "../types";

export function SettingsPage() {
  const [form, setForm] = useState<StudioSettings>({
    assistant_mode: "codex_subscription",
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [aiStatus, setAiStatus] = useState<{
    configured: boolean;
    privacy_boundary?: string;
  }>({ configured: false });
  const [factoryStatus, setFactoryStatus] = useState<FactoryStatus | null>(null);
  const [factoryError, setFactoryError] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [keyBusy, setKeyBusy] = useState(false);
  useEffect(() => {
    api
      .settings()
      .then(setForm)
      .catch((reason) =>
        setError(
          reason instanceof Error ? reason.message : "Settings unavailable",
        ),
      )
      .finally(() => setLoading(false));
    api.factoryStatus().then(setFactoryStatus).catch((reason) =>
      setFactoryError(
        reason instanceof Error ? reason.message : "Codex factory status is unavailable.",
      ),
    );
  }, []);
  useEffect(() => {
    if (form.assistant_mode !== "legacy_openai_api") return;
    api.aiStatus().then(setAiStatus).catch(() => undefined);
  }, [form.assistant_mode]);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api.saveSettings(form);
      setForm("settings" in result ? result.settings : result);
      setDirty(false);
      setMessage("Local settings saved.");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Settings were not saved",
      );
    } finally {
      setBusy(false);
    }
  }
  async function storeKey() {
    setKeyBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await api.saveAiKey(apiKey);
      setAiStatus((current) => ({ ...current, configured: result.configured }));
      setApiKey("");
      setMessage("API key stored in the operating-system keychain.");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "API key was not stored",
      );
    } finally {
      setKeyBusy(false);
    }
  }
  async function removeKey() {
    if (
      !window.confirm(
        "Remove the locally stored API key from the operating-system keychain?",
      )
    )
      return;
    setKeyBusy(true);
    setError("");
    try {
      await api.removeAiKey();
      setAiStatus((current) => ({ ...current, configured: false }));
      setMessage("API key removed from the operating-system keychain.");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "API key was not removed",
      );
    } finally {
      setKeyBusy(false);
    }
  }
  return (
    <div className="page page-narrow settings-page">
      <PageHeader
        eyebrow="Local workstation"
        title="Settings"
        description="Identity, execution defaults, and the subscription-backed Codex factory apply only to this local Research Studio."
      />
      {error && <Notice tone="danger">{error}</Notice>}
      {message && <Notice tone="success">{message}</Notice>}
      <form onSubmit={submit} onChangeCapture={() => setDirty(true)}>
        <Card className="form-section">
          <div className="form-section-heading">
            <span>01</span>
            <div>
              <h2>Researcher identity</h2>
              <p>
                Used as the default name on mechanics reviews and local records.
              </p>
            </div>
          </div>
          <Field label="Default researcher or reviewer">
            <input
              value={form.reviewer_identity || ""}
              onChange={(e) =>
                setForm({ ...form, reviewer_identity: e.target.value })
              }
              disabled={loading}
            />
          </Field>
        </Card>
        <Card className="form-section">
          <div className="form-section-heading">
            <span>02</span>
            <div>
              <h2>New-protocol defaults</h2>
              <p>
                These values prefill a new execution declaration. Every
                campaign still requires explicit confirmation.
              </p>
            </div>
          </div>
          <div className="form-grid two">
            <Field
              label="Commission (USD per contract, per side)"
              hint="One-way commission. A round trip applies this value twice."
            >
              <input
                type="number"
                min="0"
                step="any"
                value={form.default_commission_per_contract ?? 2.5}
                onChange={(e) =>
                  setForm({
                    ...form,
                    default_commission_per_contract: Number(e.target.value),
                  })
                }
              />
            </Field>
            <Field
              label="Slippage (ticks per fill)"
              hint="Applied independently to entry and exit fills."
            >
              <input
                type="number"
                min="0"
                step="any"
                value={form.default_slippage_ticks ?? 1}
                onChange={(e) =>
                  setForm({
                    ...form,
                    default_slippage_ticks: Number(e.target.value),
                  })
                }
              />
            </Field>
            <Field label="Initial account balance (USD)">
              <input
                type="number"
                min="1"
                step="any"
                value={form.default_initial_balance ?? 150000}
                onChange={(e) =>
                  setForm({
                    ...form,
                    default_initial_balance: Number(e.target.value),
                  })
                }
              />
            </Field>
            <Field
              label="Forced-flatten time"
              hint="Exchange/session time in America/New_York."
            >
              <input
                type="time"
                step="1"
                value={form.default_flatten_time || "15:55:00"}
                onChange={(e) =>
                  setForm({
                    ...form,
                    default_flatten_time: e.target.value,
                  })
                }
              />
            </Field>
          </div>
        </Card>
        <Card className="form-section">
          <div className="form-section-heading">
            <span>03</span>
            <div>
              <h2>Research assistant</h2>
              <p>
                The default uses the local Codex CLI authenticated by your
                existing ChatGPT subscription. Studio never asks for your
                ChatGPT password, session token, or subscription credential.
              </p>
            </div>
          </div>
          <Field label="Assistant mode">
            <select
              value={form.assistant_mode || "codex_subscription"}
              onChange={(event) =>
                setForm({
                  ...form,
                  assistant_mode: event.target
                    .value as StudioSettings["assistant_mode"],
                })
              }
            >
              <option value="codex_subscription">Codex via ChatGPT subscription</option>
              <option value="manual_only">Manual research only</option>
              <option value="legacy_openai_api">Legacy OpenAI API drafting</option>
            </select>
          </Field>
          {form.assistant_mode === "codex_subscription" && (
            <>
              <div className="ai-key-status">
                <div>
                  <span>Local Codex status</span>
                  <StatusBadge
                    value={
                      factoryStatus?.availability.status || "Checking"
                    }
                  />
                </div>
                <p>
                  {factoryStatus?.availability.detail ||
                    "Checking the local Codex installation and login mode."}
                </p>
              </div>
              {factoryStatus?.availability.authentication_mode === "CHATGPT" &&
                factoryStatus.availability.authenticated && (
                  <Notice tone="success">
                    Codex is authenticated through ChatGPT. No metered OpenAI
                    API key is used by the factory.
                  </Notice>
                )}
              {factoryStatus?.availability.authentication_mode === "API_KEY" && (
                <Notice tone="warning" title="Wrong authentication mode">
                  The research factory refuses API-key authentication. Use the
                  Codex login flow and choose your ChatGPT subscription.
                </Notice>
              )}
              {factoryError && <Notice tone="warning">{factoryError}</Notice>}
              <div className="form-grid two">
                <Field
                  label="Task timeout (seconds)"
                  hint="A bounded local runtime guard; allowed range is 60–7200 seconds."
                >
                  <input
                    type="number"
                    min="60"
                    max="7200"
                    value={form.codex_timeout_seconds ?? 1800}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        codex_timeout_seconds: Number(event.target.value),
                      })
                    }
                  />
                </Field>
                <Field
                  label="Maximum AI runs per day"
                  hint="AlphaQuest enforces this local trial budget before queueing."
                >
                  <input
                    type="number"
                    min="1"
                    max="200"
                    value={form.codex_max_runs_per_day ?? 12}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        codex_max_runs_per_day: Number(event.target.value),
                      })
                    }
                  />
                </Field>
              </div>
              <Notice tone="info">
                Codex receives only a bounded, hash-recorded context packet and
                returns an untrusted proposal. It runs read-only and cannot
                approve mechanics, certify a strategy, promote a candidate, or
                authorize deployment.
              </Notice>
            </>
          )}
          {form.assistant_mode === "manual_only" && (
            <Notice tone="info">
              Research remains fully usable without AI. No Codex or provider
              task will be queued in manual-only mode.
            </Notice>
          )}
        </Card>
        {form.assistant_mode === "legacy_openai_api" && (
        <details className="settings-advanced">
          <summary>
            <span>
              <strong>Legacy: OpenAI API drafting</strong>
              <small>
                Separate metered API credentials, model pinning, and retention declarations
              </small>
            </span>
            <StatusBadge
              value={aiStatus.configured ? "Configured" : "Optional"}
            />
          </summary>
        <Card className="form-section">
          <div className="form-section-heading">
            <span>04</span>
            <div>
              <h2>Legacy OpenAI API drafting</h2>
              <p>
                This compatibility path is separate from the subscription-backed
                Codex factory and may incur API usage charges.
              </p>
            </div>
          </div>
          <Notice tone="info">
            AI receives only pasted research prose or explicitly selected PDF
            text—never market data, results, raw files, web tools, or execution
            access.
          </Notice>
          <div className="ai-key-status">
            <div>
              <span>Credential status</span>
              <StatusBadge
                value={aiStatus.configured ? "Configured" : "Not configured"}
              />
            </div>
            <p>
              The key is stored in the operating-system keychain and is never
              returned to this screen.
            </p>
          </div>
          <Field
            label="OpenAI API key"
            optional
            hint="Enter a new key to add or replace the local credential."
          >
            <input
              type="password"
              autoComplete="off"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="sk-…"
            />
          </Field>
          <div className="key-actions">
            <Button
              type="button"
              variant="secondary"
              disabled={!apiKey || keyBusy}
              onClick={() => void storeKey()}
            >
              {keyBusy ? "Updating…" : "Store in keychain"}
            </Button>
            {aiStatus.configured && (
              <Button
                type="button"
                variant="danger"
                disabled={keyBusy}
                onClick={() => void removeKey()}
              >
                Remove stored key
              </Button>
            )}
          </div>
          <Field
            label="Administrator-configured model ID"
            optional
            hint="Use a pinned model ID; no moving latest alias is assumed."
          >
            <input
              value={form.openai_model || ""}
              onChange={(e) =>
                setForm({ ...form, openai_model: e.target.value })
              }
            />
          </Field>
          <Field label="Organization retention policy">
            <textarea
              rows={4}
              value={form.openai_retention_notice || ""}
              onChange={(e) =>
                setForm({ ...form, openai_retention_notice: e.target.value })
              }
            />
          </Field>
          <label className="confirmation compact">
            <input
              type="checkbox"
              checked={Boolean(form.openai_zero_data_retention_enabled)}
              onChange={(e) =>
                setForm({
                  ...form,
                  openai_zero_data_retention_enabled: e.target.checked,
                })
              }
            />
            <span>✓</span>
            <div>
              <strong>
                Administrator confirms Zero Data Retention is enabled
              </strong>
              <small>
                Do not select this unless the configured API organization
                actually has the control.
              </small>
            </div>
          </label>
          <label className="confirmation compact">
            <input
              type="checkbox"
              checked={Boolean(form.privacy_notice_acknowledged)}
              onChange={(e) =>
                setForm({
                  ...form,
                  privacy_notice_acknowledged: e.target.checked,
                })
              }
            />
            <span>✓</span>
            <div>
              <strong>I understand the selected-text privacy boundary</strong>
              <small>
                Requests use store=false, but Studio does not make unsupported
                retention promises.
              </small>
            </div>
          </label>
        </Card>
        </details>
        )}
        <div className="form-footer">
          <span className={dirty ? "settings-dirty" : "settings-saved"}>
            {dirty ? "Unsaved settings changes" : "All settings changes saved"}
          </span>
          <Button type="submit" disabled={busy || loading || !dirty}>
            {busy ? "Saving…" : "Save local settings"}
          </Button>
        </div>
      </form>
    </div>
  );
}
