import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../components/Icons";
import {
  EmptyState,
  PageHeader,
  StatusBadge,
  formatDate,
} from "../components/UI";
import { useStudio } from "../state";

export function ResearchPage() {
  const { data, loading } = useStudio();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
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
    return [...drafts, ...campaigns].filter((item) => {
      const matches = `${item.title} ${item.campaign_id} ${item.instrument}`
        .toLowerCase()
        .includes(query.toLowerCase());
      return (
        matches &&
        (filter === "all" ||
          (filter === "drafts"
            ? item.kind === "draft"
            : item.kind === "campaign"))
      );
    });
  }, [data, query, filter]);
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
            const url =
              item.kind === "draft"
                ? `/research/${item.campaign_id}/design/${item.wizard_step || 1}`
                : `/research/${item.campaign_id}/overview`;
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
                      : (item as any).workflow_blocker || item.campaign_id}
                  </small>
                </div>
                <div className="research-status">
                  <StatusBadge
                    value={
                      item.workflow_status ||
                      item.lifecycle ||
                      (item.kind === "draft" ? "Draft" : "Active")
                    }
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
    "Research brief",
    "Duplicate review",
    "Dataset",
    "Execution rules",
    "Mechanics lane",
    "Sequential variants",
    "Protocol and freeze",
  ][step - 1] || "Research brief";
