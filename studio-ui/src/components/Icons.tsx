import type { SVGProps } from "react";

export type IconName =
  | "overview"
  | "research"
  | "review"
  | "data"
  | "methods"
  | "tutorial"
  | "settings"
  | "jobs"
  | "plus"
  | "arrow"
  | "check"
  | "lock"
  | "warning"
  | "close"
  | "menu"
  | "search"
  | "chevron"
  | "clock"
  | "file"
  | "chart"
  | "shield"
  | "database"
  | "spark";

const paths: Record<IconName, React.ReactNode> = {
  overview: (
    <>
      <path d="M4 13h6V4H4v9Zm0 7h6v-3H4v3Zm10 0h6v-9h-6v9Zm0-16v3h6V4h-6Z" />
    </>
  ),
  research: (
    <>
      <path d="M9 3h6m-5 0v5l-5.6 9.2A2.5 2.5 0 0 0 6.5 21h11a2.5 2.5 0 0 0 2.1-3.8L14 8V3" />
      <path d="M7.5 15h9" />
    </>
  ),
  review: (
    <>
      <path d="M9 11.5 11 14l4.5-5" />
      <path d="M6 3h12v18H6z" />
    </>
  ),
  data: (
    <>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
    </>
  ),
  methods: (
    <>
      <path d="m4 19 6-6m4-4 6-6M14 4l6 6M4 14l6 6" />
      <path d="m12 7 5 5-5 5-5-5 5-5Z" />
    </>
  ),
  tutorial: (
    <>
      <path d="m3 6 9-4 9 4-9 4-9-4Z" />
      <path d="M7 8.5V15c3 2 7 2 10 0V8.5M21 6v8" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </>
  ),
  jobs: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  plus: (
    <>
      <path d="M12 5v14M5 12h14" />
    </>
  ),
  arrow: (
    <>
      <path d="M5 12h14m-5-5 5 5-5 5" />
    </>
  ),
  check: (
    <>
      <path d="m5 12 4 4L19 6" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </>
  ),
  warning: (
    <>
      <path d="M12 3 2.8 20h18.4L12 3Z" />
      <path d="M12 9v4m0 3.5v.1" />
    </>
  ),
  close: (
    <>
      <path d="m6 6 12 12M18 6 6 18" />
    </>
  ),
  menu: (
    <>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m16 16 4 4" />
    </>
  ),
  chevron: (
    <>
      <path d="m9 18 6-6-6-6" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  file: (
    <>
      <path d="M6 2h8l4 4v16H6z" />
      <path d="M14 2v5h5M9 12h6m-6 4h6" />
    </>
  ),
  chart: (
    <>
      <path d="M4 20V10m6 10V4m6 16v-7m4 7H2" />
    </>
  ),
  shield: (
    <>
      <path d="M12 2 4.5 5v6c0 5 3 8.5 7.5 11 4.5-2.5 7.5-6 7.5-11V5L12 2Z" />
      <path d="m8.5 12 2 2 5-5" />
    </>
  ),
  database: (
    <>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v12c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11c0 1.7 3.6 3 8 3s8-1.3 8-3" />
    </>
  ),
  spark: (
    <>
      <path d="m12 3 1.3 4.2L17.5 9l-4.2 1.8L12 15l-1.3-4.2L6.5 9l4.2-1.8L12 3Z" />
      <path d="m19 15 .7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7L19 15Z" />
    </>
  ),
};

export function Icon({
  name,
  ...props
}: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      aria-hidden="true"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
