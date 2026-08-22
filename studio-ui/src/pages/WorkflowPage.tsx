import { Link } from "react-router-dom";
import { Card, Notice, PageHeader, StatusBadge } from "../components/UI";
import { useStudio } from "../state";

const stages = [
  {
    phase: "1 · Define",
    title: "Hypothesis and success contract",
    body: "Declare objectives, research sources, the economic fingerprint, and abandonment rules before P&L is visible.",
    action: "Start new research",
    href: "/research/new",
  },
  {
    phase: "2 · De-duplicate",
    title: "Economic-edge review",
    body: "Review prior campaigns and close renamed duplicates before publication can proceed.",
    action: "Open research",
    href: "/research",
  },
  {
    phase: "3 · Bind inputs",
    title: "Governed data, execution, and target accounts",
    body: "Import or select hash-verified data, realistic costs, session rules, and one or more destination-specific account profiles.",
    action: "Open data library",
    href: "/library/data",
  },
  {
    phase: "4 · Specify mechanics",
    title: "No-code rules or certified packages",
    body: "Use a bounded completed-bar rule, an existing recipe, or a currently certified event-replay strategy package.",
    action: "Open method library",
    href: "/library/methods",
  },
  {
    phase: "5 · Verify mechanics",
    title: "Deterministic evidence and human review",
    body: "Queue the fixed mechanics replay, inspect sampled trades and event transitions, annotate each sample, and approve or reject.",
    action: "Open reviews",
    href: "/reviews?type=mechanics",
  },
  {
    phase: "6 · Test",
    title: "Scientific validity + generic investment quality",
    body: "Run the repository-owned stages through acceptance. Invalid or incomplete evidence stops closed; a generic return-quality miss is recorded but does not stop later unseen-evidence tests.",
    action: "Open campaigns",
    href: "/research",
  },
  {
    phase: "7 · Assess destination",
    title: "Challenge, funded, or live-account suitability",
    body: "After scientific validity passes, replay the exact finalized result against a selected account profile, including current acquisition or replacement costs and required attestations.",
    action: "Inspect account rules",
    href: "/library/accounts",
  },
  {
    phase: "8 · Promote cautiously",
    title: "Candidate review, forward incubation, portfolio, and deployment",
    body: "Promotion requires scientific-validity PASS plus either generic-quality PASS or PASS for one named destination profile. Approval remains candidate-only and profile-scoped.",
    action: "Open candidate reviews",
    href: "/reviews?type=candidate",
  },
];

export function WorkflowPage() {
  const { data } = useStudio();
  const activeJobs = data.jobs.filter((job) =>
    ["QUEUED", "RUNNING", "CANCEL_REQUESTED"].includes(job.state),
  ).length;
  return (
    <div className="page">
      <PageHeader
        eyebrow="End-to-end control center"
        title="Run governed research from Studio"
        description="Every routine researcher action links to its browser workflow. Each mutation still passes the same backend validation, hashes, immutable lineage, and manual gates as the command-line path."
      />
      <div className="workflow-summary metrics-grid">
        <Card><span>Drafts</span><strong>{data.drafts.length}</strong></Card>
        <Card><span>Campaigns</span><strong>{data.campaigns.length}</strong></Card>
        <Card><span>Reviews waiting</span><strong>{data.reviews.length}</strong></Card>
        <Card><span>Active jobs</span><strong>{activeJobs}</strong></Card>
      </div>
      <Notice tone="info" title="Intentional engineering boundary">
        New arbitrary Python strategy logic still requires a durable engineering handoff, repository tests, and a versioned certification manifest. Studio can run the declared certification suite and publish a fresh immutable certification identity, but it cannot accept or execute pasted code.
      </Notice>
      <div className="workflow-stage-grid">
        {stages.map((stage) => (
          <Card className="workflow-stage-card" key={stage.phase}>
            <div className="card-kicker">
              <p className="eyebrow">{stage.phase}</p>
              <StatusBadge value="Available in Studio" />
            </div>
            <h2>{stage.title}</h2>
            <p>{stage.body}</p>
            <Link className="button button-secondary" to={stage.href}>
              {stage.action}
            </Link>
          </Card>
        ))}
      </div>
      <Notice tone="warning" title="Policy is visible, not editable per strategy">
        Stage order, time windows, random seeds, run counts, objectives, and pass/fail gates remain repository-owned. A campaign may set stricter pre-PnL objectives, but Studio never offers controls that weaken the shared methodology.
      </Notice>
    </div>
  );
}
