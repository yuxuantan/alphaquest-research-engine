import { Link } from "react-router-dom";
import { useStudio } from "../state";
import {
  Button,
  Card,
  EmptyState,
  Metric,
  PageHeader,
  Skeleton,
  StatusBadge,
  formatDate,
} from "../components/UI";
import { Icon } from "../components/Icons";

export function OverviewPage() {
  const { data, loading } = useStudio();
  const activeJobs = data.jobs.filter((job) =>
    ["QUEUED", "RUNNING", "CANCEL_REQUESTED"].includes(job.state),
  );
  const latestDraft = [...data.drafts].sort((a, b) =>
    String(b.updated_at || "").localeCompare(String(a.updated_at || "")),
  )[0];
  const attention = (
    data.attention?.length ? data.attention : data.reviews
  ).slice(0, 4);
  const activeCampaigns = data.campaigns.filter((campaign) =>
    ["active", "candidate", "review_queue"].includes(
      String(campaign.lifecycle || "active"),
    ),
  );
  return (
    <div className="page page-overview">
      <PageHeader
        eyebrow="Research workspace"
        title="Good research starts before the backtest."
        description="Turn a market hypothesis into sequential governed tests, with every assumption recorded before performance is visible."
        actions={
          <Link className="button button-primary" to="/research/new">
            <Icon name="plus" />
            Start new research
          </Link>
        }
      />
      <section className="metric-grid" aria-label="Workspace summary">
        <Metric
          label="Draft research"
          value={data.drafts.length}
          detail="Ideas before publication"
        />
        <Metric
          label="Active campaigns"
          value={activeCampaigns.length}
          detail="Frozen governed protocols"
        />
        <Metric
          label="Waiting for review"
          value={data.reviews.length}
          detail="Mechanics and candidate tasks"
        />
        <Metric
          label="Running now"
          value={activeJobs.length}
          detail="Durable local worker"
        />
      </section>
      <div className="overview-grid">
        <section>
          <div className="section-heading">
            <div>
              <p className="eyebrow">Your next action</p>
              <h2>Continue research</h2>
            </div>
            <Link to="/research">View all research</Link>
          </div>
          {loading ? (
            <Card>
              <Skeleton lines={4} />
            </Card>
          ) : latestDraft ? (
            <Card className="continue-card">
              <div className="continue-icon">
                <Icon name="research" />
              </div>
              <div className="continue-content">
                <div className="card-kicker">
                  <span>
                    {latestDraft.instrument || "Futures"} ·{" "}
                    {latestDraft.timeframe || "Completed bars"}
                  </span>
                  <StatusBadge
                    value={`Step ${latestDraft.wizard_step || 1} of 7`}
                  />
                </div>
                <h3>{latestDraft.title || latestDraft.campaign_id}</h3>
                <p>{nextStepCopy(latestDraft.wizard_step || 1)}</p>
                <span className="last-saved">
                  Last saved {formatDate(latestDraft.updated_at)}
                </span>
              </div>
              <Link
                className="button button-primary"
                to={`/research/${latestDraft.campaign_id}/design/${latestDraft.wizard_step || 1}`}
              >
                Continue <Icon name="arrow" />
              </Link>
            </Card>
          ) : (
            <EmptyState
              icon="spark"
              title="Declare your first research idea"
              body="Start with the source and market behavior. Performance stays hidden until the protocol is frozen."
              action={
                <Link className="button button-primary" to="/research/new">
                  Start research
                </Link>
              }
            />
          )}
          <div className="section-heading attention-heading">
            <div>
              <p className="eyebrow">Governance inbox</p>
              <h2>Needs your attention</h2>
            </div>
            {attention.length > 0 && <Link to="/reviews">Open reviews</Link>}
          </div>
          {attention.length === 0 ? (
            <Card className="quiet-card">
              <Icon name="check" />
              <div>
                <strong>Nothing is waiting on you</strong>
                <p>
                  Blocked, review-ready, and candidate sign-off work will appear
                  here.
                </p>
              </div>
            </Card>
          ) : (
            <div className="attention-list">
              {attention.map((item: any, index: number) => (
                <Link
                  to={
                    item.type === "candidate"
                      ? "/reviews?type=candidate"
                      : "/reviews"
                  }
                  className="attention-row"
                  key={item.id || item.review_id || index}
                >
                  <span className="attention-icon">
                    <Icon
                      name={item.type === "candidate" ? "shield" : "review"}
                    />
                  </span>
                  <span>
                    <strong>
                      {item.campaign_title ||
                        item.campaign_id ||
                        "Research review"}
                    </strong>
                    <small>
                      {item.next_action ||
                        item.blocker ||
                        "Review the governed evidence."}
                    </small>
                  </span>
                  <StatusBadge value={item.status || "Needs review"} />
                  <Icon name="chevron" />
                </Link>
              ))}
            </div>
          )}
        </section>
        <aside className="overview-aside">
          <Card className="principle-card">
            <span className="principle-mark">
              <Icon name="shield" />
            </span>
            <p className="eyebrow">Scientific discipline</p>
            <h2>Evidence before confidence</h2>
            <p>
              A profitable backtest can still fail. Each variant stops at its
              first failed gate, and a PASS remains a candidate strategy only.
            </p>
            <Link to="/tutorial">
              Practice in the 15-minute tutorial <Icon name="arrow" />
            </Link>
          </Card>
          <Card className="workflow-card">
            <p className="eyebrow">Governed path</p>
            <h3>From idea to review</h3>
            <ol>
              {[
                "Declare the edge",
                "Check prior research",
                "Govern the data",
                "Freeze the first variant",
                "Approve mechanics",
                "Run staged tests",
                "Independent review",
              ].map((label, index) => (
                <li key={label}>
                  <span>{index + 1}</span>
                  {label}
                </li>
              ))}
            </ol>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function nextStepCopy(step: number): string {
  return [
    "Define the source, falsifiable hypothesis, and economic mechanism.",
    "Review possible duplicates across active, archived, and failed research.",
    "Choose bars that passed governed data intake.",
    "Confirm session, cost, sizing, and flatten rules.",
    "Choose a certified recipe, visual rule, or engineering handoff.",
    "Review and confirm the first mechanic before generating validation evidence.",
    "Read the full protocol, run preflight, and freeze it.",
  ][Math.max(0, Math.min(6, step - 1))];
}
