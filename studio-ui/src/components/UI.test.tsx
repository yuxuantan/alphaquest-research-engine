import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./UI";
import { formatJobDuration } from "./Shell";

describe("scientific status badges", () => {
  it("always renders verdict text rather than relying on color", () => {
    render(<StatusBadge value="NEEDS MANUAL REVIEW" kind="scientific" />);
    expect(screen.getByText("NEEDS MANUAL REVIEW")).toBeVisible();
  });

  it("keeps a terminal operational state readable", () => {
    render(<StatusBadge value="FAILED_OPERATIONAL" kind="operational" />);
    expect(screen.getByText("FAILED OPERATIONAL")).toBeVisible();
  });
});

describe("research job timing", () => {
  it("formats elapsed time and ETA compactly", () => {
    expect(formatJobDuration(0)).toBe("0:00");
    expect(formatJobDuration(125)).toBe("2:05");
    expect(formatJobDuration(3723)).toBe("1:02:03");
    expect(formatJobDuration(null)).toBe("—");
  });
});
