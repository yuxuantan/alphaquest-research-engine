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
import { progressPosition } from "../components/ResearchProgress";

export function OverviewPage() {
  const { data, loading } = useStudio();
  const activeJobs = data.jobs.filter((job) =>
    ["QUEUED", "RUNNING", "CANCEL_REQUESTED"].includes(job.state),
  );
  const latestDraft = [...data.drafts].sort((a, b) =>
    String(b.updated_at || "").localeCompare(String(a.updated_at || "")),
  )[0];
  const attention = (data.attention?.length ? data.attention : data.reviews)
    .filter(
      (item: any, index: number, rows: any[]) =>
        rows.findIndex(
          (candidate: any) =>
            (candidate.review_id || candidate.id || candidate.job_id) ===
            (item.review_id || item.id || item.job_id),
        ) === index,
    )
    .slice(0, 4);
  const indexedAttentionCount = data.indexed_attention?.length || 0;
  const activeCampaigns = data.campaigns.filter((campaign) =>
    ["active", "candidate", "review_queue"].includes(
      String(campaign.lifecycle || "active"),
    ),
  );
  const currentCampaign = activeCampaigns.find(
    (campaign) => campaign.workflow_context?.primary_action,
  );
  const currentAction = currentCampaign?.workflow_context?.primary_action;
  const currentProgress =
    currentCampaign?.research_progress?.campaign ||
    currentCampaign?.workflow_context?.progress;
  const currentActionHref =
    currentAction?.section === "reviews"
      ? `/reviews?type=mechanics&campaign=${encodeURIComponent(
          currentCampaign?.campaign_id || "",
        )}&attempt=${encodeURIComponent(
          currentAction?.attempt_id || "",
        )}&variant=${encodeURIComponent(currentAction?.variant_id || "")}`
      : `/research/${currentCampaign?.campaign_id}/${
          currentAction?.section || "overview"
        }?attempt=${encodeURIComponent(
          currentAction?.attempt_id || "",
        )}&variant=${encodeURIComponent(currentAction?.variant_id || "")}`;
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
          ) : currentCampaign && currentAction ? (
            <Card className="continue-card">
              <div className="continue-icon">
                <Icon name="review" />
              </div>
              <div className="continue-content">
                <div className="card-kicker">
                  <span>
                    {currentCampaign.instrument || "Futures"} ·{" "}
                    {currentCampaign.workflow_context?.target_variant_id}
                  </span>
                  <StatusBadge value={progressPosition(currentProgress)} />
                </div>
                <h3>{currentCampaign.title || currentCampaign.campaign_id}</h3>
                <p>
                  <strong>
                    {currentProgress?.current_stage_label || "Current workflow"}
                  </strong>
                  <br />
                  Next: {currentProgress?.next_action || currentAction.label}
                </p>
                <span className="last-saved">
                  {currentCampaign.workflow_context?.current_attempt_label}
                </span>
              </div>
              <Link className="button button-primary" to={currentActionHref}>
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
                      : item.type === "mechanics"
                        ? `/reviews?type=mechanics&campaign=${encodeURIComponent(
                            item.campaign_id || "",
                          )}&attempt=${encodeURIComponent(
                            item.attempt_id || "original",
                          )}&variant=${encodeURIComponent(
                            item.variant_id || "",
                          )}`
                        : "/reviews?type=items"
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
                        (item.campaign_id === currentCampaign?.campaign_id
                          ? currentAction?.label
                          : undefined) ||
                        "Review the governed evidence."}
                    </small>
                  </span>
                  <StatusBadge value={item.status || "Needs review"} />
                  <Icon name="chevron" />
                </Link>
              ))}
            </div>
          )}
          {indexedAttentionCount > 0 && (
            <Link className="indexed-attention-link" to="/reviews?type=items">
              <span>
                <Icon name="clock" />
                <span>
                  <strong>Historical indexed attention</strong>
                  <small>
                    {indexedAttentionCount} catalogue records are retained for
                    audit; they are not current workflow approvals.
                  </small>
                </span>
              </span>
              <Icon name="chevron" />
            </Link>
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
