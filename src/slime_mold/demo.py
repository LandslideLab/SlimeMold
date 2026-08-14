"""Customer-service organization demo.

The demo compares two organization designs under three supervision-budget
regimes:

* **Hierarchy** -- 3 roles across 2 levels: a team lead (span-of-control 2,
  autonomy ``approver``) supervising two customer-service agents
  (autonomy ``collaborator``). Approvals gate every agent action.
* **Flat** -- 3 self-managed customer-service agents (autonomy ``approver``,
  no manager). Agents approve their own work; no supervision interactions.

Each design is run at supervision budgets of **0%**, **50%** and **100%**
(0 / 3 / unlimited approvals per turn for the team lead), and compared on
throughput, success rate, coordination cost (messages per task, escalations)
and error rate. This is the canonical "hierarchy vs. flat under task
complexity" research use-case shipped with SlimeMold.
"""

from __future__ import annotations

import copy

from .experiments import run_spec

DEMO_SEED = 42
DEMO_TURNS = 120

# The three supervision-budget regimes: fraction of "full" capacity.
# 100% -> unlimited; 50% -> 3 approvals/turn; 0% -> none (pure delegation).
SUPERVISION_BUDGETS = {
    "0%": 0,
    "50%": 3,
    "100%": None,
}


def hierarchy_spec(budget: int | None = 3) -> dict:
    """Two-level hierarchy: team lead + 2 agents (3 roles)."""
    return {
        "name": "customer-service-hierarchy",
        "sim": {"turns": DEMO_TURNS, "seed": DEMO_SEED},
        "organization": {
            "name": "cs-hierarchy",
            "roles": [
                {"id": "lead", "name": "Team Lead",
                 "capabilities": ["review"], "autonomy": "approver"},
                {"id": "agent1", "name": "CS Agent 1",
                 "capabilities": ["t1", "t2"], "autonomy": "collaborator"},
                {"id": "agent2", "name": "CS Agent 2",
                 "capabilities": ["t1", "t3"], "autonomy": "collaborator"},
            ],
            "reporting": {"agent1": "lead", "agent2": "lead"},
        },
        "institution": {
            "delegation_strategy": "controlled",
            "supervision_budget": {"lead": budget},
            "approval_gates": [{"kind": "risk", "threshold": 0.7}],
            "escalation_timeout": 6,
            "max_wait_turns": 15,
        },
        "taskflow": {
            "arrival_rate": 1.4,
            "task_types": ["t1", "t2", "t3"],
            "complexity_mu": 0.45,
            "risk_mu": 0.35,
            "dynamism": 0.01,
            "anomaly_probability": 0.03,
            "novelty_probability": 0.05,
        },
        "knowledge": {
            "sharing_probability": 0.7,
            "half_life": 50.0,
            "revalidation_probability": 0.12,
        },
        "turnover": {"per_turn_probability": 0.002},
    }


def flat_spec() -> dict:
    """Flat design: 3 self-managed agents (3 roles, depth 1)."""
    spec = hierarchy_spec()
    spec["name"] = "customer-service-flat"
    spec["organization"]["name"] = "cs-flat"
    spec["organization"]["roles"] = [
        {"id": "agent1", "name": "CS Agent 1",
         "capabilities": ["t1", "t2"], "autonomy": "approver"},
        {"id": "agent2", "name": "CS Agent 2",
         "capabilities": ["t1", "t3"], "autonomy": "approver"},
        {"id": "agent3", "name": "CS Agent 3",
         "capabilities": ["t2", "t3"], "autonomy": "approver"},
    ]
    spec["organization"]["reporting"] = {"agent1": None, "agent2": None,
                                         "agent3": None}
    spec["institution"] = {
        "delegation_strategy": "full",
        "supervision_budget": {},
        "approval_gates": [],
        "escalation_timeout": 6,
        "max_wait_turns": 15,
    }
    return spec


# A single example spec served by the HTTP server
EXAMPLE_SPEC = hierarchy_spec(3)


def run_demo(seed: int | None = DEMO_SEED, turns: int | None = DEMO_TURNS,
             verbose: bool = True) -> list[dict]:
    """Run the full demo grid: design x budget, return summary rows."""
    rows: list[dict] = []
    designs = {"hierarchy": lambda: hierarchy_spec(0),
               "flat": lambda: flat_spec()}
    for design_name, make in designs.items():
        base = make()
        budgets = [0, 3, None] if design_name == "hierarchy" else [None]
        for budget in budgets:
            spec = copy.deepcopy(base)
            if design_name == "hierarchy":
                spec["institution"]["supervision_budget"]["lead"] = budget
            res = run_spec(spec, seed=seed, turns=turns)
            m = res.metrics
            rows.append({
                "design": design_name,
                "supervision_budget": "100%" if budget is None else
                                     (f"{budget} ({budget}/{3})"),
                "throughput": m["performance"]["throughput"],
                "success_rate": m["performance"]["success_rate"],
                "mean_flow_time": m["performance"]["mean_flow_time"],
                "messages_per_task": m["coordination"]["messages_per_task"],
                "escalations": m["coordination"]["escalations"],
                "error_rate": m["quality"]["error_rate"],
                "uncaught_risk": m["quality"]["uncaught_risk"],
                "autonomy_share": m["decision"]["autonomy_share"],
                "seed": seed,
            })
    if verbose:
        print(render_demo(rows))
    return rows


def render_demo(rows: list[dict]) -> str:
    header = (
        f"{'design':<12} {'budget':<16} {'thrpt':>6} {'success':>7} "
        f"{'flow':>5} {'msgs/task':>9} {'esc':>4} {'err':>6} {'risk':>6} "
        f"{'autonomy':>8}"
    )
    lines = ["=" * 100, "SlimeMold demo: customer-service organization", header,
             "-" * 100]
    for r in rows:
        lines.append(
            f"{r['design']:<12} {r['supervision_budget']:<16} "
            f"{r['throughput']:>6.1f} {r['success_rate']:>7.3f} "
            f"{r['mean_flow_time']:>5.1f} {r['messages_per_task']:>9.2f} "
            f"{r['escalations']:>4d} {r['error_rate']:>6.3f} "
            f"{r['uncaught_risk']:>6.3f} {r['autonomy_share']:>8.3f}"
        )
    lines.append("=" * 100)
    return "\n".join(lines)


if __name__ == "__main__":
    run_demo()
