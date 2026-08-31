import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../state", () => ({
  useStudio: () => ({ refresh: vi.fn() }),
}));

import { NewResearchPage } from "./NewResearchPage";

describe("new research objective confirmation", () => {
  it("keeps the checkbox indicator separate from the confirmation copy", () => {
    render(
      <MemoryRouter>
        <NewResearchPage />
      </MemoryRouter>,
    );

    const checkbox = screen.getByRole("checkbox", {
      name: /I confirm this performance and risk objective/i,
    });
    const confirmation = checkbox.closest("label");

    expect(confirmation).not.toBeNull();
    expect(confirmation).toHaveClass("confirmation", "compact");
    expect(confirmation?.querySelector(":scope > span > svg")).toBeInTheDocument();
    expect(
      within(confirmation as HTMLLabelElement).getByText(
        /I confirm this performance and risk objective/i,
      ).parentElement,
    ).toBe(confirmation?.querySelector(":scope > div"));
  });
});
