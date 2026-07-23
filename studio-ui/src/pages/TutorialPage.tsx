import { useState } from "react";
import { api } from "../api";
import { Icon } from "../components/Icons";
import {
  Button,
  Card,
  Notice,
  PageHeader,
  StatusBadge,
  TechnicalDetails,
  humanize,
} from "../components/UI";

const checkpoints = [
  [
    "Declare the teaching edge",
    "A completed weekday bar predicts continuation at the next bar open.",
  ],
  [
    "Review duplicates",
    "This teaching edge remains permanently isolated from the production ledger.",
  ],
  [
    "Govern synthetic bars",
    "Inspect timezone, bar-open timestamps, OHLCV checks, and constructed trend warning.",
  ],
  [
    "Confirm execution",
    "Apply costs, next-bar entry, cutoff, pessimistic fills, and no overnight exposure.",
  ],
  [
    "Freeze the first mechanic",
    "Start with one expression of the edge; later mechanics require a reviewed failure.",
  ],
  [
    "Approve implementation",
    "Self-review means mechanics match the specification—not that they are profitable.",
  ],
  [
    "Read staged results",
    "Reject promising core PnL if randomized entries perform better.",
  ],
];

export function TutorialPage() {
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  async function run() {
    setBusy(true);
    setError("");
    try {
      setResult(await api.runTutorial());
      setStep(7);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Tutorial unavailable",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page tutorial-page">
      <PageHeader
        eyebrow="Safe practice workspace"
        title="The 15-minute Research Studio walkthrough"
        description="Learn the real intake → mechanics → approval → staged-result flow on isolated synthetic bars. Nothing can enter production research."
      />
      <Notice tone="info" title="Teaching-only isolation">
        The tutorial has its own source tree, ledger, evidence, approvals, and
        job database. Its intended scientific verdict is FAIL.
      </Notice>
      <div className="tutorial-layout">
        <aside className="tutorial-steps">
          <ol>
            {checkpoints.map(([title], index) => (
              <li
                className={`${index === step ? "current" : ""} ${index < step ? "complete" : ""}`}
                key={title}
              >
                <button
                  onClick={() => index <= step && setStep(index)}
                  disabled={index > step}
                >
                  <span>
                    {index < step ? <Icon name="check" /> : index + 1}
                  </span>
                  <strong>{title}</strong>
                </button>
              </li>
            ))}
          </ol>
        </aside>
        <section className="tutorial-canvas">
          {!result ? (
            <Card className="tutorial-card">
              <p className="eyebrow">Checkpoint {step + 1} of 7</p>
              <h2>{checkpoints[step][0]}</h2>
              <p>{checkpoints[step][1]}</p>
              <div className="teaching-preview">
                <span>
                  <Icon
                    name={
                      step === 2 ? "database" : step === 6 ? "chart" : "shield"
                    }
                  />
                </span>
                <div>
                  <strong>{tutorialPreview(step).title}</strong>
                  <p>{tutorialPreview(step).body}</p>
                </div>
              </div>
              {error && <Notice tone="danger">{error}</Notice>}
              <div className="tutorial-actions">
                {step > 0 && (
                  <Button variant="secondary" onClick={() => setStep(step - 1)}>
                    Back
                  </Button>
                )}
                {step < 6 ? (
                  <Button onClick={() => setStep(step + 1)}>
                    Confirm checkpoint <Icon name="arrow" />
                  </Button>
                ) : (
                  <Button onClick={() => void run()} disabled={busy}>
                    {busy
                      ? "Running governed tutorial…"
                      : "Run isolated staged tutorial"}
                  </Button>
                )}
              </div>
            </Card>
          ) : (
            <TutorialResult
              result={result}
              onReset={() => {
                setResult(null);
                setStep(0);
              }}
            />
          )}
        </section>
      </div>
    </div>
  );
}

function TutorialResult({
  result,
  onReset,
}: {
  result: any;
  onReset: () => void;
}) {
  const matrix = result.stage_matrix || [];
  return (
    <>
      <Card className="tutorial-verdict">
        <span>
          <Icon name="warning" />
        </span>
        <div>
          <p className="eyebrow">Final research verdict</p>
          <h2>{result.research_verdict || "FAIL"}</h2>
          <p>
            Promising limited-core PnL did not beat seeded randomized entries.
            The correct decision is rejection, not a rescue disguised as
            validation.
          </p>
        </div>
        <StatusBadge
          value={result.research_verdict || "FAIL"}
          kind="scientific"
        />
      </Card>
      <div className="stage-matrix compact-matrix">
        <div className="stage-row stage-head">
          <span>Variant</span>
          <span>Verdict</span>
          <span>First failed gate</span>
        </div>
        {matrix.map((row: any, index: number) => (
          <div className="stage-row" key={index}>
            <strong>{row.variant || row.variant_id || `v0${index + 1}`}</strong>
            <StatusBadge value={row.research_verdict || row.verdict} />
            <span>
              {humanize(
                row.first_failed_gate ||
                  row.failed_stage ||
                  row.first_failed_or_unresolved_gate,
              )}
            </span>
          </div>
        ))}
      </div>
      <Notice tone="warning" title="Full methodology remains NOT_RUN">
        Ten synthetic sessions cannot honestly satisfy walk-forward, Monte
        Carlo, incubation, or locked acceptance. This is a teaching boundary—not
        a shorter path to PASS.
      </Notice>
      <Button variant="secondary" onClick={onReset}>
        Restart tutorial
      </Button>
      <TechnicalDetails>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </TechnicalDetails>
    </>
  );
}
function tutorialPreview(step: number) {
  return [
    {
      title: "Falsifiable before profitable",
      body: "The claim can be disproved and records a known market-wide drift failure.",
    },
    {
      title: "No renamed edge",
      body: "Deterministic fingerprinting protects the ledger from duplicate research.",
    },
    {
      title: "Causal, disclosed bars",
      body: "Synthetic construction, timestamp meaning, and every quality check remain visible.",
    },
    {
      title: "Realistic fills",
      body: "Costs and forced flatten apply before any metric is calculated.",
    },
    {
      title: "Value-independent differences",
      body: "Names or parameter-only changes cannot count as distinct variants.",
    },
    {
      title: "Implementation, not desirability",
      body: "Review reconciles trades to the frozen mechanics specification.",
    },
    {
      title: "Randomized benchmark decides",
      body: "Positive PnL is insufficient if arbitrary entry timing performs better.",
    },
  ][step];
}
