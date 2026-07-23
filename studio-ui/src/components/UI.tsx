import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { Icon, type IconName } from "./Icons";

export function StatusBadge({
  value,
  kind,
}: {
  value?: string | null;
  kind?: "scientific" | "operational" | "neutral";
}) {
  const label = value || "Pending";
  const normalized = label.toLowerCase().replaceAll("_", " ");
  const tone =
    normalized.includes("pass") ||
    normalized.includes("succeed") ||
    normalized.includes("approved") ||
    normalized.includes("complete")
      ? "positive"
      : normalized.includes("fail") ||
          normalized.includes("reject") ||
          normalized.includes("cancel")
        ? "negative"
        : normalized.includes("manual") ||
            normalized.includes("block") ||
            normalized.includes("review")
          ? "warning"
          : normalized.includes("running") ||
              normalized.includes("queue") ||
              normalized.includes("active")
            ? "info"
            : "neutral";
  return (
    <span
      className={`status-badge status-${tone}`}
      data-kind={kind || "neutral"}
    >
      <span className="status-dot" aria-hidden="true" />
      {label.replaceAll("_", " ")}
    </span>
  );
}

export function Button({
  variant = "primary",
  icon,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  icon?: IconName;
}) {
  return (
    <button className={`button button-${variant}`} {...props}>
      {icon && <Icon name={icon} />}
      <span>{children}</span>
    </button>
  );
}

export function Card({
  className = "",
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={`card ${className}`} {...props} />;
}

export function EmptyState({
  icon = "research",
  title,
  body,
  action,
}: {
  icon?: IconName;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} />
      </span>
      <h3>{title}</h3>
      <p>{body}</p>
      {action}
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
  optional,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  optional?: boolean;
}) {
  return (
    <label className={`field ${error ? "field-error" : ""}`}>
      <span className="field-label">
        {label}
        {optional && <span>Optional</span>}
      </span>
      {children}
      {hint && !error && <small>{hint}</small>}
      {error && (
        <small className="error-text" role="alert">
          {error}
        </small>
      )}
    </label>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warning" | "danger" | "success";
  title?: string;
  children: ReactNode;
}) {
  const icon: IconName =
    tone === "success" ? "check" : tone === "info" ? "shield" : "warning";
  return (
    <div
      className={`notice notice-${tone}`}
      role={tone === "danger" ? "alert" : "status"}
    >
      <Icon name={icon} />
      <div>
        {title && <strong>{title}</strong>}
        <div>{children}</div>
      </div>
    </div>
  );
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton" aria-label="Loading" role="status">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} />
      ))}
    </div>
  );
}

export function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode;
  detail?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

export function TechnicalDetails({ children }: { children: ReactNode }) {
  return (
    <details className="technical-details">
      <summary>Technical details</summary>
      <div>{children}</div>
    </details>
  );
}

export function formatDate(value?: string): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

export function humanize(value?: string): string {
  if (!value) return "Not available";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
