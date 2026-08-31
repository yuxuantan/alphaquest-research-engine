import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icons";
import { progressPosition } from "../components/ResearchProgress";
import {
  EmptyState,
  PageHeader,
  StatusBadge,
  formatDate,
} from "../components/UI";
import { useStudio } from "../state";

export function researchRecordHref(item: any): string {
  if (item.kind === "draft") {
    return `/research/${item.campaign_id}/design/${item.wizard_step || 1}`;
  }

  const workflow = item.workflow_context || {};
  const action = workflow.primary_action || {};
  const attemptId = workflow.current_attempt_id || action.attempt_id || "";
  const variantId = workflow.target_variant_id || action.variant_id || "";
  const query = new URLSearchParams();
  if (attemptId) query.set("attempt", attemptId);
  if (variantId) query.set("variant", variantId);

  const suffix = query.size ? `?${query.toString()}` : "";
  return `/research/${item.campaign_id}/overview${suffix}`;
}

export function ResearchPage() {
  const { data, loading } = useStudio();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [verdict, setVerdict] = useState("all");
  const [sort, setSort] = useState("attention");
  const rows = useMemo(() => {
    const drafts = data.drafts.map((item) => ({
      ...item,
      kind: "draft",
      lifecycle: item.frozen ? "Frozen draft" : "Draft",
    }));
    const campaigns = data.campaigns.map((item) => ({
      ...item,
      kind: "campaign",
    }));
    return [...drafts, ...campaigns]
      .filter((item) => {
        const matches = `${item.title} ${item.campaign_id} ${item.instrument}`
          .toLowerCase()
          .includes(query.toLowerCase());
        const workflow = (item as any).workflow_context || {};
        const scientificStatus = String(
          workflow.scientific_status || item.lifecycle || "",
        ).toLowerCase();
        return (
          matches &&
          (filter === "all" ||
            (filter === "drafts"
              ? item.kind === "draft"
              : item.kind === "campaign")) &&
          (verdict === "all" ||
            (verdict === "attention"
              ? scientificStatus.includes("manual") ||
                scientificStatus.includes("pending")
              : scientificStatus === verdict))
        );
      })
      .sort((left, right) => {
        if (sort === "title")
          return String(left.title || left.campaign_id).localeCompare(
            String(right.title || right.campaign_id),
          );
        if (sort === "updated")
          return String(right.updated_at || "").localeCompare(
            String(left.updated_at || ""),
          );
        const priority = (item: any) => {
          const status = String(
            item.workflow_context?.scientific_status || item.lifecycle || "",
          );
          if (status.includes("NEEDS MANUAL REVIEW")) return 0;
          if (item.kind === "draft") return 1;
          if (status === "FAIL") return 3;
          return 2;
        };
        return priority(left) - priority(right);
      });
  }, [data, query, filter, verdict, sort]);
  return (
    <div className="page">
      <PageHeader
        eyebrow="Research"
        title="All research"
        description="One place for ideas, frozen protocols, evidence, and explicit follow-up attempts."
        actions={
          <Link className="button button-primary" to="/research/new">
            <Icon name="plus" />
            Start new research
          </Link>
        }
      />
      <div className="toolbar" role="search">
        <label className="search-box">
          <Icon name="search" />
          <span className="sr-only">Search research</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by title, market, or edge…"
          />
        </label>
        <div className="segmented" aria-label="Research status filter">
          {[
            ["all", "All"],
            ["drafts", "Drafts"],
            ["published", "Published"],
          ].map(([value, label]) => (
            <button
              key={value}
              className={filter === value ? "selected" : ""}
              onClick={() => setFilter(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="research-view-controls" aria-label="Research view controls">
        <label>
          <span>Scientific status</span>
          <select value={verdict} onChange={(event) => setVerdict(event.target.value)}>
            <option value="all">All statuses</option>
            <option value="attention">Needs attention</option>
            <option value="pass">PASS</option>
            <option value="fail">FAIL</option>
          </select>
        </label>
        <label>
          <span>Sort by</span>
          <select value={sort} onChange={(event) => setSort(event.target.value)}>
            <option value="attention">Next action</option>
            <option value="updated">Recently updated</option>
            <option value="title">Title</option>
          </select>
        </label>
        <span>{rows.length} visible research records</span>
      </div>
      {loading ? (
        <div className="research-list loading-list">
          <span />
          <span />
          <span />
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon="research"
          title={query ? "No matching research" : "No research yet"}
          body={
            query
              ? "Try a broader search or clear the filter."
              : "A governed study starts with a falsifiable idea—not a backtest result."
          }
          action={
            !query && (
              <Link className="button button-primary" to="/research/new">
                Start research
              </Link>
            )
          }
        />
      ) : (
        <div className="research-list" role="list">
          {rows.map((item) => {
            const workflow = (item as any).workflow_context || {};
            const progress =
              (item as any).research_progress?.campaign || workflow.progress;
            const action = workflow.primary_action || {};
            const url = researchRecordHref(item);
            return (
              <Link
                className="research-row"
                to={url}
                key={`${item.kind}-${item.campaign_id}`}
                role="listitem"
              >
                <div className="research-market">
                  {item.instrument || "—"}
                  <small>{item.timeframe || "Bars"}</small>
                </div>
                <div className="research-title">
                  <span>{item.title || item.campaign_id}</span>
                  <small>
                    {item.kind === "draft"
                      ? `Step ${item.wizard_step || 1} of 7 · ${nextLabel(item.wizard_step || 1)}`
                      : `${progressPosition(progress)} · ${progress?.current_stage_label || "Stage unavailable"} · ${progress?.variant_id || workflow.target_variant_id || "Variant unavailable"}`}
                  </small>
                  {item.kind === "campaign" && (
                    <small className="research-next-action">
                      {(item as any).workflow_blocker ? "Blocked" : "Next"}:{" "}
                      {(item as any).workflow_blocker ||
                        progress?.next_action ||
                        action.label ||
                        "Inspect governed campaign"}
                    </small>
                  )}
                </div>
                <div className="research-status">
                  <StatusBadge
                    value={
                      workflow.scientific_status ||
                      item.lifecycle ||
                      (item.kind === "draft" ? "Draft" : "Active")
                    }
                    kind={item.kind === "campaign" ? "scientific" : undefined}
                  />
                  <small>Updated {formatDate(item.updated_at)}</small>
                </div>
                <Icon name="chevron" />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

const nextLabel = (step: number) =>
  [
    "Goals and research brief",
    "Duplicate review",
    "Dataset",
    "Execution rules",
    "Mechanics lane",
    "Sequential variants",
    "Protocol and freeze",
  ][step - 1] || "Goals and research brief";
