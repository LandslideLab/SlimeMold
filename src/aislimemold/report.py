"""ODD protocol model descriptions and reproduction bundles.

ABM methodology requires models to be described so readers can judge
reproducibility and robustness. SlimeMold ships an **ODD** (Overview, Design
concepts, Details) report generator that produces a structured description of a
simulation spec, and a *reproduction bundle*: the exact spec, engine version,
seed(s) and a tiny Python runner so anyone can regenerate the results.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .__version__ import __version__

_ENGINE_VERSION = __version__


def engine_version() -> str:
    return _ENGINE_VERSION


@dataclass
class ODDReport:
    """An ODD-compliant description of a model + reproduction metadata."""

    spec: dict
    seed: int | None = None
    note: str = ""

    def render(self) -> str:
        spec = self.spec
        org = spec.get("organization", {})
        inst = spec.get("institution", {})
        tf = spec.get("taskflow", {})
        kn = spec.get("knowledge", {})
        turn = spec.get("turnover", {})
        sim = spec.get("sim", {})

        roles = org.get("roles", [])
        n_roles = len(roles)
        reporting = org.get("reporting", {})
        n_edges = sum(1 for v in reporting.values() if v)

        lines: list[str] = []
        lines.append("=" * 72)
        lines.append("ODD Protocol Description -- SlimeMold")
        lines.append(f"Model: {spec.get('name', 'organization')}")
        lines.append(f"Engine version: {engine_version()}")
        lines.append("=" * 72)

        lines.append("\n1. Overview")
        lines.append("-" * 72)
        lines.append("1.1 Purpose: simulate how organization design (reporting")
        lines.append("    topology, delegation/supervision institutions, knowledge")
        lines.append("    mechanisms, task-flow environment and membership")
        lines.append("    turnover) shapes organizational performance, coordination")
        lines.append("    cost, quality, decision behaviour, learning and resilience.")
        lines.append(f"1.2 Entities: {n_roles} roles connected by {n_edges} reporting")
        lines.append(f"    edges; tasks of {len(tf.get('task_types', []))} types;")
        lines.append("    knowledge items; members.")
        lines.append("1.3 Scales: turn-based discrete time;")
        lines.append(f"    {sim.get('turns', 100)} turns per run;")
        lines.append(f"    task arrival rate {tf.get('arrival_rate', 1.0)}/turn.")
        lines.append("1.4 Observation: full event log, message log, per-turn")
        lines.append("    timeline, aggregate metrics (performance, coordination,")
        lines.append("    quality, decision, knowledge, resilience).")

        lines.append("\n2. Design Concepts")
        lines.append("-" * 72)
        lines.append("2.1 Theoretical background: contingency theory (design fits")
        lines.append("    environment), agency theory (delegation vs. monitoring),")
        lines.append("    organizational learning (crystallization, sharing,")
        lines.append("    half-life, revalidation), coordination theory (message")
        lines.append("    volume, waiting, escalation).")
        lines.append("2.2 Emergence: organization-level outcomes emerge from")
        lines.append("    individual agent decisions and the institutional rules.")
        lines.append("2.3 Adaptation: agents learn via the knowledge mechanism;")
        lines.append("    the environment shifts regimes (dynamism).")
        lines.append("2.4 Objectives: no global optimizer; agents follow policies;")
        lines.append("    design comparison uses statistical tests on metrics.")
        lines.append("2.5 Interaction: message bus only; tasks flow along the")
        lines.append("    reporting chain; approvals/consultations consume the")
        lines.append("    manager's supervision budget.")
        lines.append("2.6 Stochasticity: single seeded RNG with per-subsystem")
        lines.append("    streams; everything reproducible from the seed.")
        lines.append("2.7 Collectives: roles grouped by reporting topology;")
        lines.append("    knowledge shared along reporting edges.")
        lines.append("2.8 Observation/detection: metrics engine aggregates the")
        lines.append("    event log; resilience computed around turnover events.")

        lines.append("\n3. Details")
        lines.append("-" * 72)
        lines.append(f"3.1 Initialization: seed={self.seed or sim.get('seed')};")
        lines.append("    members start with experience 0.5 and empty knowledge.")
        lines.append("3.2 Input data: role capabilities/autonomy from DSL spec;")
        lines.append(f"    institution strategy={inst.get('delegation_strategy')};")
        lines.append(f"    gates={inst.get('approval_gates', [])};")
        lines.append(f"    supervision budget={inst.get('supervision_budget', {})};")
        lines.append(f"    escalation timeout={inst.get('escalation_timeout')};")
        lines.append(f"    max wait={inst.get('max_wait_turns')}.")
        lines.append("3.3 Submodels: ScriptedAgent policy (error probability, ")
        lines.append("    delegation, escalation, risk aversion); knowledge")
        lines.append("    mechanism (crystallization, sharing, half-life, ")
        lines.append(f"    revalidation with p={kn.get('revalidation_probability')});")
        lines.append(f"    task flow (dynamism={tf.get('dynamism')}, "
                     f"anomaly p={tf.get('anomaly_probability')});")
        lines.append(f"    turnover p={turn.get('per_turn_probability')} "
                     f"per member per turn.")
        lines.append("3.4 Implementation detail: run loop order per turn is fixed:")
        lines.append("    turnover -> environment -> arrivals -> approvals ->")
        lines.append("    execution -> timeouts -> knowledge. RNG child streams")
        lines.append("    are derived from the master seed by SHA-256 tags.")

        if self.note:
            lines.append("\nNote: " + self.note)
        lines.append("\n" + "=" * 72)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "engine_version": engine_version(),
            "seed": self.seed,
            "spec": self.spec,
            "odd": self.render(),
            "note": self.note,
        }


def reproduction_bundle(spec: dict, seed: int, out_dir: str,
                        note: str = "") -> str:
    """Write a reproduction bundle (spec, metadata, runner) to ``out_dir``.

    Returns the path of the created bundle directory.
    """
    os.makedirs(out_dir, exist_ok=True)
    report = ODDReport(spec, seed=seed, note=note)
    with open(os.path.join(out_dir, "ODD.txt"), "w", encoding="utf-8") as fh:
        fh.write(report.render())
    meta = report.to_dict()
    meta["reproduce"] = (
        "python -m aislimemold.reproduce --bundle-dir . --seed "
        f"{seed} --turns {spec.get('sim', {}).get('turns', 100)}"
    )
    with open(os.path.join(out_dir, "metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "spec.yaml"), "w", encoding="utf-8") as fh:
        _write_spec_yaml(fh, spec)
    with open(os.path.join(out_dir, "reproduce.py"), "w", encoding="utf-8") as fh:
        fh.write(_RUNNER_SCRIPT)
    return out_dir


def _write_spec_yaml(fh, spec: dict, indent: int = 0) -> None:
    pad = " " * indent
    for key, value in spec.items():
        if isinstance(value, dict):
            if not value:
                fh.write(f"{pad}{key}: {{}}\n")
                continue
            fh.write(f"{pad}{key}:\n")
            _write_spec_yaml(fh, value, indent + 2)
        elif isinstance(value, list):
            if not value:
                fh.write(f"{pad}{key}: []\n")
                continue
            fh.write(f"{pad}{key}:\n")
            for item in value:
                if isinstance(item, dict):
                    fh.write(f"{pad}  -\n")
                    _write_spec_yaml(fh, item, indent + 4)
                else:
                    fh.write(f"{pad}  - {_scalar_yaml(item)}\n")
        else:
            fh.write(f"{pad}{key}: {_scalar_yaml(value)}\n")


def _scalar_yaml(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        if " " in v or v in ("", "None", "null"):
            return f"'{v}'"
        return v
    if v is None:
        return "null"
    return str(v)


_RUNNER_SCRIPT = '''#!/usr/bin/env python3
"""Regenerate a SlimeMold run from a reproduction bundle.

Usage:  python reproduce.py [--seed N] [--turns N]
"""
import argparse
import json
import os

from aislimemold.dsl import build_spec
from aislimemold.simulation import SimulationRunner

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--turns", type=int, default=None)
    parser.add_argument("--out", default=os.path.join(HERE, "result.json"))
    args = parser.parse_args()

    with open(os.path.join(HERE, "spec.yaml"), encoding="utf-8") as fh:
        spec = fh.read()
    with open(os.path.join(HERE, "metadata.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    seed = args.seed if args.seed is not None else meta["seed"]
    built = build_spec(spec)
    built.sim.seed = seed
    if args.turns:
        built.sim.turns = args.turns
    runner = SimulationRunner(
        built.org, built.institution, built.taskflow,
        built.turnover, built.knowledge, built.sim,
    )
    for rid, policy in built.policy_overrides.items():
        runner.set_policy(rid, policy)
    result = runner.run()
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2)
    print(f"wrote {args.out}: performance={result.metrics['performance']}")


if __name__ == "__main__":
    main()
'''
