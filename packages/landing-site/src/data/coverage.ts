/**
 * Which states are in the Explorer, and how completely.
 *
 * - "full": the whole standards document (the `_trimmed` tier or the
 *   state's own document), passed the per-state quality gate.
 * - "partial": a subset of the document's pages only. As of 2026-11-06
 *   every loaded state is partial.
 * - "planned": being processed next; not in the Explorer yet.
 *
 * Move a state to "full" only after its quality gate is recorded
 * (tasking/outreach_plan.md, "Quality gate per state").
 */

export type CoverageStatus = "full" | "partial" | "planned";

export interface StateCoverage {
  code: string;
  name: string;
  documentYear: number | null;
  status: CoverageStatus;
}

export const coverage: StateCoverage[] = [
  { code: "AZ", name: "Arizona", documentYear: 2018, status: "partial" },
  { code: "CA", name: "California", documentYear: 2021, status: "partial" },
  { code: "CO", name: "Colorado", documentYear: 2020, status: "full" },
  { code: "KY", name: "Kentucky", documentYear: 2021, status: "full" },
  { code: "NV", name: "Nevada", documentYear: 2023, status: "partial" },
  { code: "TX", name: "Texas", documentYear: 2022, status: "partial" },
  { code: "FL", name: "Florida", documentYear: null, status: "planned" },
];

export const COVERAGE_LABEL: Record<CoverageStatus, string> = {
  full: "Full document (preview)",
  partial: "Partial",
  planned: "Coming soon",
};
