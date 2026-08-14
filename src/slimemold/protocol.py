"""Headless JSON protocol: run / compare / scan / report from the CLI or API.

This module is the contract between the Python engine and any client (the web
testbed, notebooks, CI). Everything the engine produces is JSON-serializable;
everything a client sends is a plain spec dict (see ``slimemold.dsl``).

CLI usage::

    python -m slimemold run --spec spec.yaml --out result.json
    python -m slimemold compare --spec-a a.yaml --spec-b b.yaml --metric throughput
    python -m slimemold scan --spec spec.yaml --param supervision_budget.mgr --values 0,3,5
    python -m slimemold report --spec spec.yaml --out-dir bundle
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import experiments
from .dsl import build_spec, parse_yaml
from .simulation import SimulationRunner


def load_spec(path: str) -> dict:
    """Load a spec from a JSON or YAML file (or a raw dict)."""
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        data = parse_yaml(text)
    if not isinstance(data, dict):
        raise TypeError(f"spec {path} must be a mapping")
    return data


def run_command(spec: dict, seed: int | None = None, turns: int | None = None) -> dict:
    """Execute a single run and return the JSON-serializable result."""
    built = build_spec(spec)
    if seed is not None:
        built.sim.seed = seed
    if turns is not None:
        built.sim.turns = turns
    runner = SimulationRunner(
        built.org, built.institution, built.taskflow,
        built.turnover, built.knowledge, built.sim,
    )
    for rid, policy in built.policy_overrides.items():
        runner.set_policy(rid, policy)
    result = runner.run()
    out = result.to_dict()
    out["spec"] = spec
    return out


def compare_command(spec_a: dict, spec_b: dict, metric: str = "throughput",
                    reps: int = 8, seed: int = 42, test: str = "mann_whitney",
                    turns: int | None = None) -> dict:
    res = experiments.compare(spec_a, spec_b, metric=metric, reps=reps,
                              seed=seed, test=test, turns=turns)
    return res.to_dict()


def scan_command(spec: dict, parameter: str, values, metric: str = "throughput",
                 seed: int = 42, turns: int | None = None, reps: int = 1) -> dict:
    res = experiments.scan(spec, parameter, values, metric=metric, seed=seed,
                           turns=turns, reps=reps)
    return res.to_dict()


def report_command(spec: dict, out_dir: str, seed: int = 42, note: str = "") -> dict:
    path = experiments.report(spec, out_dir, seed=seed, note=note)
    return {"out_dir": path, "status": "ok"}


# ------------------------------------------------------------------- CLI


def _parse_values(raw: str):
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return [int(v) if v.strip().lstrip("-").isdigit()
            else float(v) if _is_float(v) else v for v in raw.split(",")]


def _is_float(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slimemold",
        description="SlimeMold: human + AI organization design simulation testbed",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run a single simulation")
    p_run.add_argument("--spec", required=True)
    p_run.add_argument("--out", default="result.json")
    p_run.add_argument("--seed", type=int, default=None)
    p_run.add_argument("--turns", type=int, default=None)

    p_cmp = sub.add_parser("compare", help="compare two designs A vs B")
    p_cmp.add_argument("--spec-a", required=True)
    p_cmp.add_argument("--spec-b", required=True)
    p_cmp.add_argument("--metric", default="throughput")
    p_cmp.add_argument("--reps", type=int, default=8)
    p_cmp.add_argument("--seed", type=int, default=42)
    p_cmp.add_argument("--test", default="mann_whitney",
                       choices=["mann_whitney", "t", "auto"])
    p_cmp.add_argument("--turns", type=int, default=None)
    p_cmp.add_argument("--out", default=None)

    p_scan = sub.add_parser("scan", help="parameter sensitivity scan")
    p_scan.add_argument("--spec", required=True)
    p_scan.add_argument("--param", required=True)
    p_scan.add_argument("--values", required=True)
    p_scan.add_argument("--metric", default="throughput")
    p_scan.add_argument("--seed", type=int, default=42)
    p_scan.add_argument("--turns", type=int, default=None)
    p_scan.add_argument("--reps", type=int, default=1)
    p_scan.add_argument("--out", default=None)

    p_rep = sub.add_parser("report", help="write ODD report + reproduction bundle")
    p_rep.add_argument("--spec", required=True)
    p_rep.add_argument("--out-dir", default="slimemold_bundle")
    p_rep.add_argument("--seed", type=int, default=42)
    p_rep.add_argument("--note", default="")

    p_server = sub.add_parser("serve", help="run the headless HTTP server")
    p_server.add_argument("--host", default="127.0.0.1")
    p_server.add_argument("--port", type=int, default=8642)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            spec = load_spec(args.spec)
            out = run_command(spec, seed=args.seed, turns=args.turns)
            _write_json(args.out, out)
            print(f"wrote {args.out} (seed={out['config']['seed']})")
        elif args.command == "compare":
            a = load_spec(args.spec_a)
            b = load_spec(args.spec_b)
            out = compare_command(a, b, metric=args.metric, reps=args.reps,
                                  seed=args.seed, test=args.test, turns=args.turns)
            dest = args.out or "compare.json"
            _write_json(dest, out)
            s = out["statistics"]
            print(
                f"metric={args.metric}  mean A={s['mean_a']} mean B={s['mean_b']}\n"
                f"cohens_d={s['cohens_d']}  p={s['p']} "
                f"({'significant' if s['significant'] else 'not significant'})"
            )
        elif args.command == "scan":
            spec = load_spec(args.spec)
            out = scan_command(spec, args.param, _parse_values(args.values),
                               metric=args.metric, seed=args.seed, turns=args.turns,
                               reps=args.reps)
            dest = args.out or "scan.json"
            _write_json(dest, out)
            print(out)
        elif args.command == "report":
            spec = load_spec(args.spec)
            out = report_command(spec, args.out_dir, seed=args.seed, note=args.note)
            print(f"wrote ODD report + reproduction bundle to {out['out_dir']}")
        elif args.command == "serve":
            from .server import serve
            serve(host=args.host, port=args.port)
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # pragma: no cover - CLI error path  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


if __name__ == "__main__":
    sys.exit(main())
