import { describe, expect, it } from "vitest";
import {
  moduleAvailabilityLabel,
  publicationAvailableStrategyPackages,
  strategyPackageLabel,
} from "./strategyAvailability";

describe("publicationAvailableStrategyPackages", () => {
  it("requires the server's explicit fail-closed publication decision", () => {
    const packages = publicationAvailableStrategyPackages([
      {
        name: "current_package",
        strategy_package: true,
        certification_status: "certified",
        certification_current: true,
        certification_errors: [],
        available_for_publication: true,
        strategy_label: "Yush Orderflow Range Reversal",
      },
      {
        name: "hash_drifted_package",
        strategy_package: true,
        certification_status: "certified",
        certification_current: false,
        certification_errors: ["implementation hash has drifted"],
        available_for_publication: false,
      },
      {
        name: "legacy_response_without_availability",
        strategy_package: true,
        certification_status: "certified",
      },
      {
        name: "ordinary_entry_module",
        strategy_package: false,
        available_for_publication: true,
      },
    ]);

    expect(packages.map((item) => item.name)).toEqual(["current_package"]);
    expect(strategyPackageLabel(packages[0])).toBe(
      "Yush Orderflow Range Reversal",
    );
    expect(strategyPackageLabel({ name: "fallback", strategy_label: "  " })).toBe(
      undefined,
    );
    expect(moduleAvailabilityLabel(packages[0])).toBe("Certified");
    expect(
      moduleAvailabilityLabel({
        name: "stale",
        strategy_package: true,
        certification_status: "certified",
        certification_current: false,
        available_for_publication: false,
      }),
    ).toBe("Certification stale");
    expect(
      moduleAvailabilityLabel({
        name: "hidden",
        strategy_package: true,
        certification_status: "certified",
        certification_current: true,
        available_for_publication: false,
      }),
    ).toBe("Unavailable for publication");
  });
});
