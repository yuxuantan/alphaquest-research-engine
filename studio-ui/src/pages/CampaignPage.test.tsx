import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import {
  FollowUpDecisionGuide,
  Mechanics,
  ParentAttemptGuide,
  ParameterHeatmap,
  Protocol,
  ResultTradeChart,
  Results,
  Testing,
} from "./CampaignPage";
import { api } from "../api";

const gridRows = [
  {
    run_id: 13,
    "event.params.max_aoi_width_points": 3,
    "event.params.entry_offset_ticks": 2,
    "event.params.stop_offset_ticks": 2,
    total_trades: 37,
    net_profit: -1110,
    profit_factor: 0.479,
    profitable: false,
    benchmark_passed: false,
  },
  {
    run_id: 14,
    "event.params.max_aoi_width_points": 3,
    "event.params.entry_offset_ticks": 2,
    "event.params.stop_offset_ticks": 3,
    total_trades: 37,
    net_profit: -1147.5,
    profit_factor: 0.471,
    profitable: false,
    benchmark_passed: false,
  },
];

const detail = {
  attempts: [
    {
      attempt_id: "replication",
      attempt_kind: "replication",
      target_variant_id: "v01",
      dataset_bindings: [{ variant_id: "v01" }],
    },
  ],
  workflow_context: {
    current_attempt_id: "replication",
    target_variant_id: "v01",
  },
  stage_matrix: [
    {
      variant: "v01",
      "research verdict": "FAIL",
      "operational state": "SUCCEEDED",
      "first failed or unresolved gate": "limited_core_grid_test",
    },
  ],
  latest_results: {
    v01: {
      run_id: "attempt-replication",
      verdict: "FAIL",
      failed_stage: "limited_core_grid_test",
      metrics: {
        net_profit_after_costs: { value: -1110, reason: null },
        total_trades: { value: 37, reason: null },
      },
      stage_criteria: [
        {
          stage: "limited_core_grid_test",
          metric: "summary.percentage_profitable_iterations",
          operator: ">=",
          threshold: { value: 0.7 },
          actual: { value: 0.09 },
          result: "FAIL",
        },
      ],
      core_grid_inspection: {
        available: true,
        default_run_id: 13,
        parameter_columns: [
          "event.params.max_aoi_width_points",
          "event.params.entry_offset_ticks",
          "event.params.stop_offset_ticks",
        ],
        iteration_count: 100,
        iteration_reports_retained: false,
      },
      artifact_previews: {
        parameter_neighbors: {
          available: true,
          rows: 2,
          columns: Object.keys(gridRows[0]),
          preview_rows: gridRows,
          truncated: false,
        },
      },
    },
  },
  attempt_results: {
    replication: {
      v01: {
        run_id: "attempt-replication",
        verdict: "FAIL",
        failed_stage: "limited_core_grid_test",
        metrics: {
          net_profit_after_costs: { value: -1110, reason: null },
          total_trades: { value: 37, reason: null },
        },
        stage_criteria: [
          {
            stage: "limited_core_grid_test",
            metric: "summary.percentage_profitable_iterations",
            operator: ">=",
            threshold: { value: 0.7 },
            actual: { value: 0.09 },
            result: "FAIL",
          },
        ],
        core_grid_inspection: {
          available: true,
          default_run_id: 13,
          parameter_columns: [
            "event.params.max_aoi_width_points",
            "event.params.entry_offset_ticks",
            "event.params.stop_offset_ticks",
          ],
          iteration_count: 100,
          iteration_reports_retained: false,
        },
        artifact_previews: {
          parameter_neighbors: {
            available: true,
            rows: 2,
            columns: Object.keys(gridRows[0]),
            preview_rows: gridRows,
            truncated: false,
          },
        },
      },
    },
  },
};

describe("core-grid result inspection", () => {
  it("defaults to the declared configuration and switches only iteration metrics", () => {
    const view = render(
      <MemoryRouter>
        <Results detail={detail} />
      </MemoryRouter>,
    );

    const selector = screen.getByRole("combobox", {
      name: "Core-grid iteration",
    });
    expect(selector).toHaveValue("13");
    expect(
      screen.getByRole("heading", {
        name: "Declared-default fixed-config metrics",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "This selector changes inspection metrics only. The scientific verdict and profitable-iteration gate above remain based on all 100 hash-bound grid combinations.",
      ),
    ).toBeVisible();

    fireEvent.change(selector, { target: { value: "14" } });

    expect(
      screen.getByRole("heading", {
        name: "Iteration 14 summary metrics",
      }),
    ).toBeVisible();
    expect(screen.getAllByText("-1,147.5").length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "This run retained summary metrics for every iteration, but not per-iteration trade logs or equity curves. The reporting evidence below remains scoped to the declared-default fixed configuration.",
      ),
    ).toBeVisible();
    expect(screen.getAllByText("FAIL").length).toBeGreaterThan(0);
  });

  it("offers a direct path from an unfinished current attempt to finalized evidence", () => {
    const { container } = render(
      <MemoryRouter>
        <Results
          detail={{
            attempts: [
              {
                attempt_id: "original",
                attempt_kind: "original",
                dataset_bindings: [{ variant_id: "v01" }],
              },
              {
                attempt_id: "current_correction",
                attempt_kind: "pre_pnl_mechanics_correction",
                dataset_bindings: [{ variant_id: "v02" }],
              },
            ],
            workflow_context: {
              current_attempt_id: "current_correction",
              target_variant_id: "v02",
            },
            attempt_results: {
              original: {
                v01: {
                  run_id: "original-result",
                  verdict: "FAIL",
                  metrics: { total_trades: { value: 20 } },
                  stage_criteria: [],
                  artifact_previews: {},
                },
              },
            },
          }}
        />
      </MemoryRouter>,
    );
    const view = within(container);

    expect(
      view.getByRole("heading", {
        name: "No finalized performance result for v02",
      }),
    ).toBeVisible();
    fireEvent.click(
      view.getByRole("button", {
        name: "View latest finalized · v01",
      }),
    );

    expect(view.getAllByText("FAIL").length).toBeGreaterThan(0);
    expect(view.getByLabelText("Variant result")).toHaveValue("v01");
  });
});

describe("parameter heatmap", () => {
  it("renders two parameters as labelled axes and keeps losing results red", () => {
    const rows = [
      {
        run_id: 1,
        "event.params.sweep_atr_fraction": 0.1,
        "event.params.maximum_stop_atr_multiple": 1.25,
        net_profit: -9695.59,
      },
      {
        run_id: 2,
        "event.params.sweep_atr_fraction": 0.2,
        "event.params.maximum_stop_atr_multiple": 1.25,
        net_profit: -11388.6,
      },
      {
        run_id: 3,
        "event.params.sweep_atr_fraction": 0.1,
        "event.params.maximum_stop_atr_multiple": 1.5,
        net_profit: -12786.85,
      },
      {
        run_id: 4,
        "event.params.sweep_atr_fraction": 0.2,
        "event.params.maximum_stop_atr_multiple": 1.5,
        net_profit: -15232.4,
      },
    ];
    render(
      <ParameterHeatmap
        parameterColumns={[
          "event.params.sweep_atr_fraction",
          "event.params.maximum_stop_atr_multiple",
        ]}
        preview={{
          available: true,
          columns: Object.keys(rows[0]),
          preview_rows: rows,
        }}
      />,
    );

    const matrix = screen.getByRole("table", {
      name: "Net Profit by Sweep Atr Fraction and Maximum Stop Atr Multiple",
    });
    expect(within(matrix).getAllByRole("columnheader")).toHaveLength(3);
    expect(within(matrix).getAllByRole("rowheader")).toHaveLength(2);
    expect(
      within(matrix).getByRole("cell", {
        name: /Sweep Atr Fraction 0.1.*Maximum Stop Atr Multiple 1.25.*Net Profit -9,695.59/,
      }),
    ).toBeVisible();
    const cells = within(matrix).getAllByRole("cell");
    expect(cells).toHaveLength(4);
    cells.forEach((cell) => expect(cell).toHaveAttribute("data-tone", "negative"));
    expect(
      screen.getByText("All displayed net profit results are below zero."),
    ).toBeVisible();
  });
});

describe("execution-level trade chart", () => {
  it("omits an unretained target and separates nearby price levels", () => {
    render(
      <ResultTradeChart
        trade={{
          trade_id: 1,
          entry_price: 4368.5,
          stop_price: 4365.5,
          target_price: null,
          exit_price: 4365.25,
          entry_timestamp: "2021-07-13 14:00:00.000000-04:00",
          exit_timestamp: "2021-07-13 14:08:36-04:00",
        }}
        excursion={{ mae: 2.75, mfe: 3 }}
      />,
    );

    const chart = screen.getByRole("img", { name: "Trade price levels" });
    expect(screen.queryByText(/Target Undefined/)).not.toBeInTheDocument();
    expect(within(chart).queryByText(/^Target/)).not.toBeInTheDocument();
    const levelLines = [...chart.querySelectorAll("line[data-level]")];
    expect(levelLines).toHaveLength(3);
    const linePositions = levelLines.map((line) => Number(line.getAttribute("y1")));
    expect(Math.max(...linePositions) - Math.min(...linePositions)).toBeGreaterThan(100);
    const labelPositions = [...chart.querySelectorAll("text")].map((label) =>
      label.getAttribute("y"),
    );
    expect(new Set(labelPositions).size).toBe(labelPositions.length);
    expect(screen.getByText("8.6 min")).toBeVisible();
  });
});

describe("follow-up creation guidance", () => {
  it("shows when to use and avoid each follow-up type", () => {
    const onSelect = vi.fn();
    render(
      <FollowUpDecisionGuide
        selected="replication"
        onSelect={onSelect}
        kinds={[
          {
            value: "replication",
            label: "Exact replication",
            summary: "Run the same frozen attempt again.",
            use_when: "The attempt was interrupted.",
            do_not_use_when: "Anything research-defining must change.",
            available: true,
          },
          {
            value: "data_refresh",
            label: "Governed data refresh",
            summary: "Replace only the dataset.",
            use_when: "Corrected governed data is available.",
            do_not_use_when: "Mechanics must change.",
            available: true,
          },
        ]}
      />,
    );

    expect(screen.getByText("The attempt was interrupted.")).toBeVisible();
    expect(
      screen.getByText("Anything research-defining must change."),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("radio", { name: /Governed data refresh/ }),
    );
    expect(onSelect).toHaveBeenCalledWith("data_refresh");
  });

  it("disables only the follow-up types rejected by their own policy", () => {
    const onSelect = vi.fn();
    const view = render(
      <FollowUpDecisionGuide
        selected="replication"
        onSelect={onSelect}
        kinds={[
          {
            value: "replication",
            label: "Exact replication",
            summary: "Run the same frozen attempt again.",
            use_when: "The attempt was interrupted.",
            do_not_use_when: "Anything research-defining must change.",
            available: true,
          },
          {
            value: "pre_pnl_mechanics_correction",
            label: "Pre-PnL mechanics correction",
            summary: "Correct one reviewed mechanic.",
            use_when: "No performance evidence exists.",
            do_not_use_when: "Performance evidence already exists.",
            available: false,
            unavailable_reason: "This parent already has performance evidence.",
          },
        ]}
      />,
    );

    const guide = within(view.container);
    expect(guide.getByRole("radio", { name: /Exact replication/ })).toBeEnabled();
    expect(
      guide.getByRole("radio", { name: /Pre-PnL mechanics correction/ }),
    ).toBeDisabled();
    expect(
      guide.getByText("This parent already has performance evidence."),
    ).toBeVisible();
  });

  it("warns when the selected parent is an earlier branch point", () => {
    render(
      <ParentAttemptGuide
        kind={{
          parent_rule: "Select the exact terminal FAIL being rescued.",
        }}
        parent={{
          attempt_id: "original",
          attempt_kind: "original",
          lineage_label: "Earlier branch point with 1 follow-up",
          reason: "Frozen original publication.",
          branch_warning:
            "This attempt already has a follow-up. Choosing it creates a separate branch.",
        }}
      />,
    );

    expect(
      screen.getByText("Select the exact terminal FAIL being rescued."),
    ).toBeVisible();
    expect(
      screen.getByText("You are creating a separate branch"),
    ).toBeVisible();
  });
});

describe("variant-aware testing attempt selection", () => {
  it("defaults to the attempt containing v02 and names the exact target variant", () => {
    render(
      <MemoryRouter>
        <Testing
          detail={{
            campaign: {
              campaign_id: "demo",
              variant_count: 2,
            },
            next_variant: { current_variant_id: "v02" },
            stage_matrix: [{ variant: "v01" }, { variant: "v02" }],
            attempts: [
              {
                attempt_id: "original",
                attempt_kind: "original",
                dataset_bindings: [
                  { variant_id: "v01" },
                  { variant_id: "v02" },
                ],
              },
              {
                attempt_id: "replication_old",
                attempt_kind: "replication",
                dataset_bindings: [{ variant_id: "v01" }],
              },
            ],
            mechanics_approval: {
              original: {
                all_approved: false,
                variants: [
                  { variant_id: "v02", status: "BLOCKED" },
                ],
              },
              replication_old: {
                all_approved: true,
                variants: [
                  { variant_id: "v01", status: "APPROVED_FOR_TESTING" },
                ],
              },
            },
          }}
          onRefresh={vi.fn()}
        />
      </MemoryRouter>,
    );

    const selector = screen.getByRole("combobox", {
      name: "Attempt identity",
    });
    expect(selector).toHaveValue("original");
    expect(
      screen.getByRole("option", {
        name: "Original · date not recorded · original · v01 + v02 · targets v02",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", {
        name: "Generate mechanics evidence · v02",
      }),
    ).toBeVisible();
    expect(screen.getByText("Selected attempt targets v02")).toBeVisible();

    fireEvent.change(selector, {
      target: { value: "replication_old" },
    });

    expect(
      screen.getByRole("button", {
        name: "Generate mechanics evidence · v01",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(/This is a historical attempt and does not contain/),
    ).toBeVisible();
  });

  it("exposes the full test suite only after mechanics approval", () => {
    render(
      <MemoryRouter>
        <Testing
          detail={{
            campaign: {
              campaign_id: "yush_orderflow_range",
              variant_count: 2,
            },
            workflow_context: {
              current_attempt_id: "mechanics_correction_1",
              target_variant_id: "v02",
            },
            attempts: [
              {
                attempt_id: "mechanics_correction_1",
                attempt_kind: "pre_pnl_mechanics_correction",
                dataset_bindings: [{ variant_id: "v02" }],
              },
            ],
            mechanics_approval: {
              mechanics_correction_1: {
                all_approved: true,
                approved_count: 1,
                required_count: 1,
                variants: [
                  {
                    variant_id: "v02",
                    status: "APPROVED_FOR_TESTING",
                  },
                ],
              },
            },
          }}
          onRefresh={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("button", {
        name: "Run full test suite · v02",
      }),
    ).toBeVisible();
    expect(
      screen.queryByText("Performance testing remains hidden"),
    ).not.toBeInTheDocument();
  });

  it("replaces rerun controls with explicit finalization-only recovery", async () => {
    const recovery = vi.spyOn(api, "recoverFinalization").mockResolvedValue({
      recovered: true,
      source_job_id: "job-1",
      research_verdict: "FAIL",
      finalization: {},
      next_action: "Open Results.",
    });
    const onRefresh = vi.fn().mockResolvedValue({});
    render(
      <MemoryRouter>
        <Testing
          detail={{
            campaign: { campaign_id: "demo", variant_count: 1 },
            workflow_context: {
              current_attempt_id: "protocol_1",
              target_variant_id: "v03",
            },
            attempts: [
              {
                attempt_id: "protocol_1",
                attempt_kind: "pre_pnl_protocol_declaration",
                dataset_bindings: [{ variant_id: "v03" }],
              },
            ],
            stage_matrix: [
              {
                variant: "v03",
                "operational state": "FAILED_OPERATIONAL",
                "first failed or unresolved gate":
                  "result_bundle_v2_finalization",
              },
            ],
            mechanics_approval: {
              protocol_1: {
                all_approved: true,
                variants: [
                  { variant_id: "v03", status: "APPROVED_FOR_TESTING" },
                ],
              },
            },
          }}
          onRefresh={onRefresh}
        />
      </MemoryRouter>,
    );

    expect(
      screen.queryByRole("button", { name: "Run full test suite · v03" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Research finished; publication did not"),
    ).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Recover finalized evidence · v03",
      }),
    );

    await waitFor(() =>
      expect(recovery).toHaveBeenCalledWith("demo", "protocol_1"),
    );
    expect(onRefresh).toHaveBeenCalled();
  });

  it("routes a finalized immutable attempt to Results instead of offering a rerun", () => {
    render(
      <MemoryRouter>
        <Testing
          detail={{
            campaign: { campaign_id: "demo", variant_count: 1 },
            workflow_context: {
              current_attempt_id: "protocol_1",
              target_variant_id: "v03",
            },
            attempts: [
              {
                attempt_id: "protocol_1",
                attempt_kind: "pre_pnl_protocol_declaration",
                dataset_bindings: [{ variant_id: "v03" }],
              },
            ],
            stage_matrix: [
              {
                variant: "v03",
                "operational state": "SUCCEEDED",
                "first failed or unresolved gate": "limited_core_grid_test",
              },
            ],
            attempt_results: {
              protocol_1: {
                v03: { research_verdict: "FAIL" },
              },
            },
            mechanics_approval: {
              protocol_1: {
                all_approved: true,
                variants: [
                  { variant_id: "v03", status: "APPROVED_FOR_TESTING" },
                ],
              },
            },
          }}
          onRefresh={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(
      screen.queryByRole("button", { name: "Run full test suite · v03" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "View finalized result · v03" }),
    ).toHaveAttribute(
      "href",
      "/research/demo/results?attempt=protocol_1&variant=v03",
    );
  });
});

describe("governed protocol and mechanics disclosure", () => {
  it("shows the economic edge, research basis, and known failure modes", () => {
    render(
      <Protocol
        detail={{
          campaign: {
            title: "Failed auction reclaim",
            instrument: "ES",
            timeframe: "1m",
          },
          protocol: {
            hypothesis: "Outside aggression fails and returns to fair value.",
            market_behavior: "Price rejects a developing value edge.",
            causal_mechanism: "Passive liquidity absorbs aggressive flow.",
            signal_inputs: ["Developing profile", "Signed delta"],
            market_context: "Morning ES auction.",
            holding_period: "Intraday only.",
            supporting_sources: [
              {
                title: "Order-flow study",
                authors: ["A. Researcher"],
                year: 2025,
                link: "https://example.test/research",
                doi: "10.1000/example",
                relevance: "Supports short-horizon order-flow impact.",
              },
            ],
            known_failure_modes: ["A reclaim can fail again."],
            source_identity: { frozen: true },
          },
        }}
      />,
    );

    expect(screen.getByText("What should repeat")).toBeVisible();
    expect(
      screen.getByText("Passive liquidity absorbs aggressive flow."),
    ).toBeVisible();
    expect(screen.getByText("Order-flow study")).toBeVisible();
    expect(screen.getByText("A reclaim can fail again.")).toBeVisible();
  });

  it("offers the immutable pre-PnL protocol action for an eligible legacy attempt", () => {
    render(
      <MemoryRouter>
        <Protocol
          detail={{
            campaign: {
              campaign_id: "demo",
              title: "Legacy campaign",
            },
            protocol: {
              research_objectives: {},
              source_identity: { frozen: true },
              legacy_pre_pnl_action: {
                available: true,
                parent_attempt_id: "mechanics_correction_1",
                target_variant_id: "v03",
              },
            },
          }}
          onRefresh={vi.fn()}
        />
      </MemoryRouter>,
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Create pre-PnL protocol from legacy campaign",
      }),
    );

    expect(screen.getByText("Immutable lineage and fresh approval")).toBeVisible();
    expect(screen.getByLabelText("Development goal")).toBeVisible();
    expect(screen.getByLabelText(/Primary account benchmark/)).toBeVisible();
    expect(
      screen.getByText(
        "I understand approval is limited to the exact frozen primary profile",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(
        "This copies the selected attempt's certified mechanics, parameter grid, dataset, and execution into a new attempt. Repository methodology stays fixed; declared objectives may only tighten its criteria. The new config hash clears inherited evidence references, so the existing mechanics approval does not carry forward.",
      ),
    ).toBeVisible();

    fireEvent.click(
      screen.getByRole("button", { name: "Create immutable protocol attempt" }),
    );
    expect(
      screen.getByText(
        "Enter the researcher identity before creating the protocol.",
      ),
    ).toBeVisible();
  });

  it("selects an immutable attempt and displays exact rules and hashes", () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/research/demo/mechanics?attempt=correction_1&variant=v02",
        ]}
      >
        <Mechanics
          detail={{
            campaign: { campaign_id: "demo" },
            mechanics: {
              default_attempt_id: "correction_1",
              attempts: [
                {
                  attempt_id: "correction_1",
                  attempt_kind: "pre_pnl_mechanics_correction",
                  target_variant_id: "v02",
                  variants: [
                    {
                      variant_id: "v02",
                      title: "Failed-auction reclaim",
                      is_attempt_target: true,
                      expresses_edge: "Wait for an outside auction to fail.",
                      rules: {
                        entry: "Enter after a causal reclaim.",
                        stop: "Stop beyond the excursion.",
                        target_and_time_exit: "Target frozen POC.",
                        forced_flatten: {
                          flatten_time: "11:00:00",
                          timezone: "America/New_York",
                          overnight_allowed: false,
                        },
                      },
                      causal_availability: "Only observed events are used.",
                      session_and_timeframe: {
                        timeframe: "events",
                        session_start: "09:30:00",
                        session_end: "11:00:00",
                        timezone: "America/New_York",
                        rationale: "Use ordered trade events.",
                      },
                      fixed_defaults: { excursion_ticks: 2 },
                      entry_criteria: [
                        {
                          criterion: "First trade one tick back inside",
                          reason:
                            "This is the minimum unambiguous ES reclaim and prevents selecting a later favorable event.",
                          support: "Causality and discrete-price definition",
                        },
                      ],
                      parameter_grid: {
                        "event.params.excursion_ticks": [2, 4],
                      },
                      parameter_combination_count: 2,
                      certification: {
                        strategy_id: "failed_auction",
                        implementation_version: 3,
                        implementation_sha256: "implementation-hash",
                        manifest_sha256: "manifest-hash",
                      },
                      config_sha256: "config-hash",
                      mechanic_signature: "mechanic-hash",
                      mechanics_approval: {
                        status: "NEEDS_MANUAL_REVIEW",
                        errors: ["Five samples require review."],
                        note: "This is the target variant.",
                      },
                    },
                  ],
                },
              ],
            },
          }}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("combobox", { name: "Immutable attempt" }),
    ).toHaveValue("correction_1");
    expect(screen.getByText("Enter after a causal reclaim.")).toBeVisible();
    expect(screen.getByText("Why every condition exists")).toBeVisible();
    expect(
      screen.getByText("First trade one tick back inside"),
    ).toBeVisible();
    expect(
      screen.getByText("Causality and discrete-price definition"),
    ).toBeVisible();
    expect(screen.getByText("implementation-hash")).toBeVisible();
    expect(screen.getByText("Five samples require review.")).toBeVisible();
  });
});
