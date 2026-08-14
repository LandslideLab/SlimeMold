"""Experiment modes: compare, scan and report.

Three experiment archetypes are provided, matching the way organizational
design research is actually done:

* **compare** -- run two designs A and B for ``reps`` seeded repetitions each,
  compute a chosen metric per run, and report descriptive statistics plus a
  significance test (default Mann-Whitney U, Welch's t optional) with effect
  size. This answers "is design A better than B?".
* **scan** -- sweep a single parameter (span-of-control, depth, supervision
  budget, turnover rate, ...) across a range of values, running each point and
  reporting the metric curve. This answers "how does the metric respond to the
  design knob?".
* **report** -- produce an ODD protocol description plus a reproduction bundle
  for a single design (used to make a specific run shareable and auditable).

All modes are deterministic: every repetition uses a derived seed so the whole
experiment can be re-run byte-for-byte.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field

from . import stats
from .dsl import build_spec
from .report import reproduction_bundle
from .rng import _derive_seed
from .simulation import SimulationResult, SimulationRunner

METRIC_PATHS = {
    "throughput": ("performance", "throughput"),
    "success_rate": ("performance", "success_rate"),
    "mean_flow_time": ("performance", "mean_flow_time"),
    "messages_per_task": ("coordination", "messages_per_task"),
    "mean_waiting_turns": ("coordination", "mean_waiting_turns"),
    "escalations": ("coordination", "escalations"),
    "error_rate": ("quality", "error_rate"),
    "uncaught_risk": ("quality", "uncaught_risk"),
    "autonomy_share": ("decision", "autonomy_share"),
    "mean_decision_latency": ("decision", "mean_decision_latency"),
    "retention_rate": ("knowledge", "retention_rate"),
    "revalidation_rate": ("knowledge", "revalidation_rate"),
}


def metric_value(metrics: dict, metric: str) -> float:
    """Extract a scalar metric from the metrics dict by path or key."""
    if metric in metrics:
        value = metrics[metric]
        return float(value) if isinstance(value, (int, float)) else float("nan")
    path = METRIC_PATHS.get(metric)
    if path is None:
        raise KeyError(f"unknown metric: {metric}")
    node = metrics
    for part in path:
        node = node[part]
    return float(node)


def build_runner(spec: dict, seed: int) -> tuple[SimulationRunner, int]:
    """Build a runner from a spec dict, forcing ``seed`` and returning it."""
    built = build_spec(spec)
    if seed is not None:
        built.sim.seed = seed
    runner = SimulationRunner(
        built.org, built.institution, built.taskflow,
        built.turnover, built.knowledge, built.sim,
    )
    for rid, policy in built.policy_overrides.items():
        runner.set_policy(rid, policy)
    return runner, built.sim.seed


def run_spec(spec: dict, seed: int | None = None,
             turns: int | None = None) -> SimulationResult:
    """Run a single spec (helper used by all modes)."""
    runner, _ = build_runner(spec, seed)
    if turns is not None:
        runner.config.turns = turns
    return runner.run()


# ------------------------------------------------------------------ compare


@dataclass
class CompareResult:
    """Results of a paired-design comparison."""

    spec_a: dict
    spec_b: dict
    metric: str
    reps: int
    values_a: list[float]
    values_b: list[float]
    statistics: dict
    seeds: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mode": "compare",
            "metric": self.metric,
            "reps": self.reps,
            "values_a": [round(v, 4) for v in self.values_a],
            "values_b": [round(v, 4) for v in self.values_b],
            "statistics": self.statistics,
            "seeds": self.seeds,
            "spec_a": self.spec_a,
            "spec_b": self.spec_b,
        }

    def render(self) -> str:
        s = self.statistics
        lines = [
            "=" * 60,
            f"COMPARE  metric={self.metric}  reps={self.reps}",
            f"A: mean={s['mean_a']} sd={s['sd_a']}",
            f"B: mean={s['mean_b']} sd={s['sd_b']}",
            f"Cohens d = {s['cohens_d']}",
            f"{s['test']}: p = {s['p']} ({'significant' if s['significant'] else 'not significant'})",
            "=" * 60,
        ]
        return "\n".join(lines)


def compare(spec_a: dict, spec_b: dict, metric: str = "throughput",
            reps: int = 8, seed: int | None = 42, test: str = "mann_whitney",
            turns: int | None = None) -> CompareResult:
    """Compare design A vs design B on a metric with a significance test."""
    values_a: list[float] = []
    values_b: list[float] = []
    seeds: list[int] = []
    for rep in range(reps):
        rep_seed = _derive_seed(seed if seed is not None else 0, f"compare:{rep}")
        seeds.append(rep_seed)
        ra = run_spec(spec_a, seed=rep_seed, turns=turns)
        rb = run_spec(spec_b, seed=rep_seed, turns=turns)
        values_a.append(metric_value(ra.metrics, metric))
        values_b.append(metric_value(rb.metrics, metric))
    report = stats.significance_report(values_a, values_b, test=test)
    return CompareResult(
        spec_a=spec_a,
        spec_b=spec_b,
        metric=metric,
        reps=reps,
        values_a=values_a,
        values_b=values_b,
        statistics=report,
        seeds=seeds,
    )


# ---------------------------------------------------------------------- scan


@dataclass
class ScanResult:
    """Results of a parameter sensitivity scan."""

    spec_template: dict
    parameter: str
    path: str
    values: list
    metric: str
    metric_values: list[float]
    seeds: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "mode": "scan",
            "parameter": self.parameter,
            "path": self.path,
            "values": list(self.values),
            "metric": self.metric,
            "metric_values": [round(v, 4) for v in self.metric_values],
            "seeds": self.seeds,
            "spec_template": self.spec_template,
        }

    def render(self) -> str:
        lines = [
            "=" * 60,
            f"SCAN  {self.parameter} -> {self.metric}",
        ]
        for v, m in zip(self.values, self.metric_values):
            lines.append(f"  {v!s:<12} -> {m:.4f}")
        lines.append("=" * 60)
        return "\n".join(lines)


def set_param(spec: dict, path: list[str], value) -> dict:
    """Return a deep copy of *spec* with the param at *path* set to *value*."""
    import copy

    out = copy.deepcopy(spec)
    node = out
    for part in path[:-1]:
        node = node[part]
    node[path[-1]] = value
    return out


def scan(spec_template: dict, parameter: str, values,
         metric: str = "throughput", seed: int | None = 42,
         turns: int | None = None, reps: int = 1) -> ScanResult:
    """Sweep *parameter* (dot path in the spec) across *values*."""
    path = parameter.split(".")
    metric_values: list[float] = []
    seeds: list[int] = []
    for i, value in enumerate(values):
        spec = set_param(spec_template, path, value)
        rep_seed = _derive_seed(seed if seed is not None else 0, f"scan:{i}")
        seeds.append(rep_seed)
        vals: list[float] = []
        for r in range(reps):
            res = run_spec(spec, seed=_derive_seed(rep_seed, f"rep:{r}"), turns=turns)
            vals.append(metric_value(res.metrics, metric))
        metric_values.append(sum(vals) / len(vals) if vals else 0.0)
    return ScanResult(
        spec_template=spec_template,
        parameter=parameter,
        path=path,
        values=list(values),
        metric=metric,
        metric_values=metric_values,
        seeds=seeds,
    )


# -------------------------------------------------------------------- report


def report(spec: dict, out_dir: str | None = None,
           seed: int | None = 42, note: str = "") -> str:
    """Write an ODD protocol description + reproduction bundle.

    Returns the bundle directory path.
    """
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="slime_mold_bundle_")
    reproduction_bundle(spec, seed, out_dir, note=note)
    return out_dir
