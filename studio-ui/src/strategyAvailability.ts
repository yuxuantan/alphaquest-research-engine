import type { ModuleSummary } from "./types";

export function publicationAvailableStrategyPackages(
  modules: ModuleSummary[],
): ModuleSummary[] {
  return modules.filter(
    (item) =>
      item.strategy_package === true &&
      item.available_for_publication === true,
  );
}

export function strategyPackageLabel(module: ModuleSummary): string | undefined {
  const label = module.strategy_label?.trim();
  return label || undefined;
}

export function moduleAvailabilityLabel(module: ModuleSummary): string {
  if (module.certification_status === "developer_only") return "Developer only";
  if (module.strategy_package === true) {
    if (module.certification_current !== true) return "Certification stale";
    if (module.available_for_publication !== true) {
      return "Unavailable for publication";
    }
  }
  return "Certified";
}
