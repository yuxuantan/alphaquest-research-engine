import type { ResearchStage, VariantProgress } from "../types";
import { Card } from "./UI";

export function progressPosition(progress?: VariantProgress | null): string {
  if (!progress) return "Stage not available";
  return `Stage ${progress.current_step} of ${progress.total_steps}`;
}

function groupedStages(stages: ResearchStage[]) {
  const groups: Array<{ phase: string; stages: ResearchStage[] }> = [];
  for (const stage of stages) {
    const current = groups.at(-1);
    if (!current || current.phase !== stage.phase) {
      groups.push({ phase: stage.phase, stages: [stage] });
    } else {
      current.stages.push(stage);
    }
  }
  return groups;
}

function statusLabel(status: ResearchStage["status"]): string {
  return {
    complete: "Complete",
    current: "Current",
    ready: "Ready to run",
    upcoming: "Upcoming",
    locked: "Locked",
    failed: "Failed — stopped",
    blocked: "Blocked",
    not_applicable: "Not reached",
  }[status];
}

export function ResearchFlow({ progress }: { progress?: VariantProgress | null }) {
  if (!progress?.stages?.length) return null;
  const groups = groupedStages(progress.stages);
  return (
    <Card className="research-flow-card">
      <div className="research-flow-heading">
        <div>
          <p className="eyebrow">Step-by-step research flow</p>
          <h2>
            {progressPosition(progress)} · {progress.current_stage_label}
          </h2>
          <p>
            Campaign position is controlled by current sequential variant{" "}
            <strong>{progress.variant_id}</strong>. A completed operational step
            does not replace its scientific gate.
          </p>
        </div>
        <div className="research-flow-next">
          <span>Next required action</span>
          <strong>{progress.next_action}</strong>
        </div>
      </div>
      <div className="research-flow-phases">
        {groups.map((group) => (
          <section className="research-flow-phase" key={group.phase}>
            <h3>{group.phase}</h3>
            <ol>
              {group.stages.map((stage) => (
                <li
                  className={`research-flow-stage stage-${stage.status}`}
                  key={stage.id}
                  aria-current={
                    ["current", "ready", "failed", "blocked"].includes(
                      stage.status,
                    )
                      ? "step"
                      : undefined
                  }
                >
                  <span className="research-stage-marker" aria-hidden="true">
                    {stage.status === "complete"
                      ? "✓"
                      : stage.status === "failed"
                        ? "×"
                        : stage.step}
                  </span>
                  <span>
                    <strong>{stage.label}</strong>
                    <small>{statusLabel(stage.status)}</small>
                  </span>
                  <span className="research-stage-description">
                    {stage.description}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
      <div className="research-flow-legend" aria-label="Stage status legend">
        <span><i className="legend-complete" /> Complete</span>
        <span><i className="legend-current" /> Current or ready</span>
        <span><i className="legend-blocked" /> Failed or blocked</span>
        <span><i className="legend-locked" /> Locked or not reached</span>
      </div>
    </Card>
  );
}
