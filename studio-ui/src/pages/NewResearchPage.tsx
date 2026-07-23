import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { Button, Card, Field, Notice, PageHeader } from "../components/UI";
import { Icon } from "../components/Icons";
import { useStudio } from "../state";

export function NewResearchPage() {
  const navigate = useNavigate();
  const { refresh } = useStudio();
  const [title, setTitle] = useState("");
  const [instrument, setInstrument] = useState("ES");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.createDraft({
        title,
        instrument,
        campaign_id: slugify(title),
      });
      await refresh();
      navigate(`/research/${result.campaign_id}/design/1`);
    } catch (reason) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : "The draft could not be created.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page page-narrow">
      <Link className="back-link" to="/research">
        ← All research
      </Link>
      <PageHeader
        eyebrow="New research"
        title="What behavior do you want to test?"
        description="Start with a plain-language title. AlphaQuest creates the governed identity and keeps performance hidden while you design the protocol."
      />
      <Card className="new-study-card">
        <form onSubmit={submit}>
          {error && (
            <Notice tone="danger" title="Draft not created">
              {error}
            </Notice>
          )}
          <Field
            label="Research title"
            hint="Describe the behavior, not the hoped-for result."
          >
            <input
              autoFocus
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Opening auction continuation after imbalance"
              required
            />
          </Field>
          <fieldset>
            <legend>Market</legend>
            <div className="market-options">
              {[
                ["ES", "S&P 500 E-mini", "$50 per point"],
                ["NQ", "Nasdaq-100 E-mini", "$20 per point"],
              ].map(([symbol, name, detail]) => (
                <label
                  className={
                    instrument === symbol
                      ? "market-card selected"
                      : "market-card"
                  }
                  key={symbol}
                >
                  <input
                    type="radio"
                    name="instrument"
                    value={symbol}
                    checked={instrument === symbol}
                    onChange={() => setInstrument(symbol)}
                  />
                  <span className="market-symbol">{symbol}</span>
                  <span>
                    <strong>{name}</strong>
                    <small>{detail}</small>
                  </span>
                  <span className="radio-mark">
                    <Icon name="check" />
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <Notice tone="info" title="No result data is used">
            The next seven steps freeze the source, data, execution, and first
            mechanics before any PnL is visible.
          </Notice>
          <div className="form-footer">
            <Link className="button button-secondary" to="/research">
              Cancel
            </Link>
            <Button type="submit" disabled={busy || !title.trim()} icon="arrow">
              {busy ? "Creating…" : "Create research draft"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

function slugify(value: string): string {
  const normalized = value
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return (normalized || "research_idea").slice(0, 72).replace(/_+$/g, "");
}
