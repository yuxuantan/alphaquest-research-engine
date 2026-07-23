import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api";
import { useStudio } from "../state";
import type { JobRecord } from "../types";
import { Icon, type IconName } from "./Icons";
import { Button, Notice, StatusBadge, formatDate, humanize } from "./UI";

const navigation: Array<{
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
}> = [
  { to: "/", label: "Overview", icon: "overview", end: true },
  { to: "/research", label: "Research", icon: "research" },
  { to: "/reviews", label: "Reviews", icon: "review" },
  { to: "/library/data", label: "Data library", icon: "data" },
  { to: "/library/methods", label: "Method library", icon: "methods" },
  { to: "/tutorial", label: "Tutorial", icon: "tutorial" },
];

export function Shell() {
  const { data, error, refresh } = useStudio();
  const [navOpen, setNavOpen] = useState(false);
  const [jobsOpen, setJobsOpen] = useState(false);
  const [mobile, setMobile] = useState(
    () => window.matchMedia("(max-width: 900px)").matches,
  );
  const menuButton = useRef<HTMLButtonElement>(null);
  const navCloseButton = useRef<HTMLButtonElement>(null);
  const jobsButton = useRef<HTMLButtonElement>(null);
  const location = useLocation();
  useEffect(() => setNavOpen(false), [location.pathname]);
  useEffect(() => {
    if (navOpen) navCloseButton.current?.focus();
  }, [navOpen]);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 900px)");
    const changed = () => setMobile(media.matches);
    media.addEventListener("change", changed);
    return () => media.removeEventListener("change", changed);
  }, []);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (jobsOpen) {
        setJobsOpen(false);
        jobsButton.current?.focus();
      } else if (navOpen) {
        setNavOpen(false);
        menuButton.current?.focus();
      }
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [jobsOpen, navOpen]);
  const activeJobs = data.jobs.filter((job) =>
    ["QUEUED", "RUNNING", "CANCEL_REQUESTED"].includes(job.state),
  );
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <button
        ref={menuButton}
        className="mobile-menu icon-button"
        onClick={() => setNavOpen(true)}
        aria-label="Open navigation"
      >
        <Icon name="menu" />
      </button>
      {navOpen && (
        <button
          className="nav-scrim"
          onClick={() => {
            setNavOpen(false);
            menuButton.current?.focus();
          }}
          aria-label="Close navigation"
        />
      )}
      <aside
        className={`sidebar ${navOpen ? "sidebar-open" : ""}`}
        aria-label="Primary navigation"
        inert={(mobile && !navOpen) || jobsOpen}
      >
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <div>
            <strong>AlphaQuest</strong>
            <small>Research Studio</small>
          </div>
          <button
            ref={navCloseButton}
            className="icon-button mobile-nav-close"
            onClick={() => {
              setNavOpen(false);
              menuButton.current?.focus();
            }}
            aria-label="Close navigation"
          >
            <Icon name="close" />
          </button>
        </div>
        <NavLink to="/research/new" className="new-research">
          <Icon name="plus" /> Start new research
        </NavLink>
        <nav>
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.label === "Reviews" && data.reviews.length > 0 && (
                <span className="nav-count">{data.reviews.length}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            <Icon name="settings" />
            <span>Settings</span>
          </NavLink>
          <div className="workspace-health">
            <span className={error ? "health-dot unhealthy" : "health-dot"} />
            <div>
              <strong>
                {data.workspace?.name ||
                  data.workspace?.project_name ||
                  "Local workspace"}
              </strong>
              <small>
                {error ? "Service needs attention" : "Local services connected"}
              </small>
            </div>
          </div>
        </div>
      </aside>
      <div className="workspace" inert={jobsOpen || (mobile && navOpen)}>
        <header className="topbar">
          <div className="candidate-message">
            <Icon name="shield" />
            <span>Backtests are evidence—not trading approval.</span>
          </div>
          <button
            ref={jobsButton}
            className="job-trigger"
            onClick={() => setJobsOpen(true)}
            aria-label={`${activeJobs.length} active jobs. Open job drawer`}
          >
            <Icon name="jobs" />
            <span>Jobs</span>
            {activeJobs.length > 0 && <b>{activeJobs.length}</b>}
          </button>
        </header>
        {error && (
          <div className="service-banner">
            <Notice tone="warning" title="Local service unavailable">
              {error}{" "}
              <button className="text-button" onClick={() => void refresh()}>
                Try again
              </button>
            </Notice>
          </div>
        )}
        <main id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      {jobsOpen && (
        <JobDrawer
          jobs={data.jobs}
          onClose={() => {
            setJobsOpen(false);
            window.setTimeout(() => jobsButton.current?.focus());
          }}
          onRefresh={refresh}
        />
      )}
      <div className="sr-only" aria-live="polite">
        {activeJobs.length
          ? `${activeJobs.length} research jobs active.`
          : "No research jobs active."}
      </div>
    </div>
  );
}

function JobDrawer({
  jobs,
  onClose,
  onRefresh,
}: {
  jobs: JobRecord[];
  onClose: () => void;
  onRefresh: () => Promise<void>;
}) {
  const [cancelling, setCancelling] = useState<string | null>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => closeButton.current?.focus(), []);
  const sorted = useMemo(
    () =>
      [...jobs].sort((a, b) =>
        String(b.updated_at || "").localeCompare(String(a.updated_at || "")),
      ),
    [jobs],
  );
  async function cancel(job: JobRecord) {
    if (
      !window.confirm(
        "Request cancellation? Evidence already reserved will be preserved and the research verdict becomes NEEDS MANUAL REVIEW.",
      )
    )
      return;
    setCancelling(job.job_id);
    try {
      await api.cancelJob(job.job_id);
      await onRefresh();
    } finally {
      setCancelling(null);
    }
  }
  return (
    <>
      <button
        className="drawer-scrim"
        aria-label="Close job drawer"
        onClick={onClose}
      />
      <aside className="job-drawer drawer-open" aria-label="Research jobs">
        <div className="drawer-header">
          <div>
            <p className="eyebrow">Durable local worker</p>
            <h2>Research jobs</h2>
          </div>
          <button
            ref={closeButton}
            className="icon-button"
            onClick={onClose}
            aria-label="Close job drawer"
          >
            <Icon name="close" />
          </button>
        </div>
        <p className="drawer-intro">
          Operational progress is separate from the scientific verdict. Closing
          the browser does not stop this work.
        </p>
        <div className="job-list">
          {sorted.length === 0 && (
            <div className="drawer-empty">
              <Icon name="clock" />
              <strong>No work queued</strong>
              <span>
                Jobs will appear here after mechanics or performance submission.
              </span>
            </div>
          )}
          {sorted.map((job) => {
            const variant = job.variant_id || job.payload?.variant_id;
            const progress = job.progress_detail;
            const canCancel = [
              "QUEUED",
              "RUNNING",
              "CANCEL_REQUESTED",
            ].includes(job.state);
            return (
              <article className="job-card" key={job.job_id}>
                <div className="job-card-head">
                  <div>
                    <strong>{humanize(job.job_type || "Research job")}</strong>
                    <span>
                      {job.campaign_id}
                      {variant ? ` · ${variant}` : ""}
                    </span>
                  </div>
                  <StatusBadge value={job.state} kind="operational" />
                </div>
                {typeof job.progress === "number" && (
                  <div className="job-progress-block">
                    <div className="job-progress-heading">
                      <strong>
                        {progress?.message || humanize(progress?.phase || "Working")}
                      </strong>
                      <span>{Math.round(job.progress)}%</span>
                    </div>
                    <div
                      className="job-progress"
                      role="progressbar"
                      aria-label={progress?.message || "Research job progress"}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.round(job.progress)}
                    >
                      <span
                        style={{
                          width: `${Math.max(0, Math.min(100, job.progress))}%`,
                        }}
                      />
                    </div>
                    {progress && (
                      <div className="job-progress-detail">
                        <span>
                          {progress.completed != null && progress.total != null
                            ? `${progress.completed}/${progress.total} ${progress.unit || "items"}`
                            : humanize(progress.phase)}
                        </span>
                        <span>
                          Elapsed {formatJobDuration(progress.elapsed_seconds)}
                          {progress.eta_seconds != null
                            ? ` · about ${formatJobDuration(progress.eta_seconds)} remaining`
                            : job.state === "RUNNING"
                              ? " · estimating remaining time"
                              : ""}
                        </span>
                      </div>
                    )}
                  </div>
                )}
                {job.research_verdict && (
                  <div className="job-verdict">
                    <span>Research verdict</span>
                    <StatusBadge
                      value={job.research_verdict}
                      kind="scientific"
                    />
                  </div>
                )}
                {(job.blocked_reason || job.error) && (
                  <p className="job-error">{job.blocked_reason || job.error}</p>
                )}
                <div className="job-meta">
                  <span>Updated {formatDate(job.updated_at)}</span>
                  {canCancel && (
                    <Button
                      variant="ghost"
                      onClick={() => void cancel(job)}
                      disabled={cancelling === job.job_id}
                    >
                      {cancelling === job.job_id ? "Requesting…" : "Cancel"}
                    </Button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </aside>
    </>
  );
}

export function formatJobDuration(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const totalSeconds = Math.max(0, Math.round(value));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
