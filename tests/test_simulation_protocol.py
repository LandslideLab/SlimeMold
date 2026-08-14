"""Tests for the SimulationRunner and the JSON protocol/server."""

import json
import threading

import pytest

from slime_mold import __version__
from slime_mold.agents import DummyLLMAdapter
from slime_mold.institution import Institution
from slime_mold.organization import Organization
from slime_mold.roles import OrgRole
from slime_mold.simulation import (
    SimConfig,
    SimulationResult,
    SimulationRunner,
)
from slime_mold.tasks import TaskFlow
from slime_mold.turnover import Turnover


def build_runner(spec_dict):
    from slime_mold.dsl import build_spec

    b = build_spec(spec_dict)
    r = SimulationRunner(b.org, b.institution, b.taskflow, b.turnover,
                         b.knowledge, b.sim)
    for rid, policy in b.policy_overrides.items():
        r.set_policy(rid, policy)
    return r


def test_run_completes_and_has_metrics(built_hierarchy):
    r = build_runner(built_hierarchy.to_dict())
    result = r.run()
    assert len(result.events) > 0
    assert result.metrics["performance"]["throughput"] >= 0
    assert result.metrics["performance"]["success_rate"] <= 1.0
    assert "coordination" in result.metrics


def test_run_is_reproducible(built_hierarchy):
    spec = built_hierarchy.to_dict()
    r1 = build_runner(spec).run()
    r2 = build_runner(spec).run()
    e1 = [e.to_dict() for e in r1.events]
    e2 = [e.to_dict() for e in r2.events]
    assert e1 == e2
    assert r1.metrics == r2.metrics


def test_run_different_seeds_differ(built_hierarchy):
    spec = built_hierarchy.to_dict()
    spec["sim"]["seed"] = 1
    r1 = build_runner(spec).run()
    spec["sim"]["seed"] = 2
    r2 = build_runner(spec).run()
    assert r1.metrics["performance"]["throughput"] != \
        r2.metrics["performance"]["throughput"]


def test_supervision_enabled_switch():
    spec = {
        "sim": {"turns": 40, "seed": 3},
        "organization": {
            "roles": [
                {"id": "mgr", "capabilities": ["review"], "autonomy": "approver"},
                {"id": "a1", "capabilities": ["t1"], "autonomy": "collaborator"},
            ],
            "reporting": {"a1": "mgr"},
        },
        "institution": {"delegation_strategy": "controlled",
                        "supervision_budget": {"mgr": 0}},
        "taskflow": {"arrival_rate": 1.0, "task_types": ["t1"]},
    }
    from slime_mold.dsl import build_spec

    b = build_spec(spec)
    b.sim.supervision_enabled = False
    r = SimulationRunner(b.org, b.institution, b.taskflow, b.turnover,
                         b.knowledge, b.sim)
    result = r.run()
    assert result.metrics["coordination"]["approval_messages"] == 0


def test_no_capable_role_fails_cleanly():
    spec = {
        "sim": {"turns": 10, "seed": 1},
        "organization": {
            "roles": [{"id": "r", "capabilities": ["zz"], "autonomy": "approver"}],
            "reporting": {"r": None},
        },
        "taskflow": {"arrival_rate": 1.0, "task_types": ["t1"]},
    }
    from slime_mold.dsl import build_spec

    b = build_spec(spec)
    r = SimulationRunner(b.org, b.institution, b.taskflow, b.turnover,
                         b.knowledge, b.sim)
    result = r.run()
    assert result.metrics["performance"]["success_rate"] == 0.0


def test_llm_policy_integration():
    spec = {
        "sim": {"turns": 20, "seed": 4},
        "organization": {
            "roles": [{"id": "a1", "capabilities": ["t1"], "autonomy": "approver"}],
            "reporting": {"a1": None},
        },
        "taskflow": {"arrival_rate": 1.0, "task_types": ["t1"]},
    }
    from slime_mold.dsl import build_spec

    b = build_spec(spec)
    r = SimulationRunner(b.org, b.institution, b.taskflow, b.turnover,
                         b.knowledge, b.sim)
    r.set_policy("a1", DummyLLMAdapter())
    result = r.run()
    assert result.metrics["performance"]["n_completed"] >= 0


def test_deadlock_resolution_detected():
    spec = {
        "sim": {"turns": 60, "seed": 11},
        "organization": {
            "roles": [
                {"id": "mgr", "capabilities": ["review"], "autonomy": "approver"},
                {"id": "a1", "capabilities": ["t1"], "autonomy": "operator"},
            ],
            "reporting": {"a1": "mgr"},
        },
        "institution": {"delegation_strategy": "command",
                        "supervision_budget": {"mgr": 0},
                        "escalation_timeout": 3,
                        "max_wait_turns": 8},
        "taskflow": {"arrival_rate": 2.0, "task_types": ["t1"]},
    }
    from slime_mold.dsl import build_spec

    b = build_spec(spec)
    r = SimulationRunner(b.org, b.institution, b.taskflow, b.turnover,
                         b.knowledge, b.sim)
    result = r.run()
    deadlocks = [e for e in result.events if e.kind == "deadlock_resolved"]
    assert len(deadlocks) > 0


def test_turnover_events_recorded():
    spec = {
        "sim": {"turns": 30, "seed": 2},
        "organization": {
            "roles": [{"id": "a1", "capabilities": ["t1"], "autonomy": "approver"}],
            "reporting": {"a1": None},
        },
        "turnover": {"schedule": {5: ["a1"]}},
        "taskflow": {"arrival_rate": 1.0, "task_types": ["t1"]},
    }
    from slime_mold.dsl import build_spec

    b = build_spec(spec)
    r = SimulationRunner(b.org, b.institution, b.taskflow, b.turnover,
                         b.knowledge, b.sim)
    result = r.run()
    assert any(t == 5 for t, _ in result.turnover_events)


def test_result_to_dict_roundtrip(built_hierarchy):
    r = build_runner(built_hierarchy.to_dict())
    result = r.run()
    d = result.to_dict()
    assert d["config"]["seed"] == built_hierarchy.sim.seed
    assert d["organization"]["shape"] in ("hierarchy", "flat")
    restored = SimulationResult.from_dict(d)
    assert restored.org.shape() == result.org.shape()
    assert len(restored.tasks) == len(result.tasks)


def test_result_from_dict_missing_metrics():
    d = {
        "config": {"turns": 5, "seed": 1},
        "organization": {"roles": {}, "reporting": {}, "name": "x"},
        "institution": {},
        "taskflow": {"arrival_rate": 1.0, "task_types": ["t"]},
        "turnover": {},
        "tasks": [],
    }
    restored = SimulationResult.from_dict(d)
    assert restored.metrics == {}


def test_config_from_dict_ignores_unknown_keys():
    cfg = SimConfig.from_dict({"turns": 5, "bogus": 1})
    assert cfg.turns == 5


def test_manual_runner_construction():
    org = Organization.from_spec([OrgRole(id="a", capabilities={"t"})],
                                 {"a": None})
    inst = Institution(delegation_strategy="full")
    tf = TaskFlow(arrival_rate=0.5, task_types=["t"])
    r = SimulationRunner(org, inst, tf, Turnover(), config=SimConfig(turns=10, seed=1))
    res = r.run()
    assert res.metrics["performance"]["throughput"] >= 0


def test_metrics_dict_without_full_result():
    org = Organization.from_spec([OrgRole(id="a", capabilities={"t"})],
                                 {"a": None})
    inst = Institution(delegation_strategy="full")
    tf = TaskFlow(arrival_rate=0.5, task_types=["t"])
    r = SimulationRunner(org, inst, tf, config=SimConfig(turns=10, seed=1))
    r.run(collect_metrics=False)
    m = r.metrics_dict()
    assert m["performance"]["success_rate"] >= 0


# ------------------------------------------------- protocol / server


def test_protocol_run_command(tmp_path):
    from slime_mold.dsl import build_spec
    from slime_mold.protocol import run_command

    spec = build_spec(
        "demos/cs_flat.yaml"
    ).to_dict()
    out = run_command(spec, seed=42, turns=10)
    assert "metrics" in out
    assert out["config"]["seed"] == 42
    assert out["config"]["turns"] == 10


def test_protocol_compare_scan_commands():
    from slime_mold.demo import flat_spec, hierarchy_spec
    from slime_mold.protocol import compare_command, scan_command

    c = compare_command(hierarchy_spec(3), flat_spec(), metric="throughput",
                        reps=2)
    assert c["statistics"]["mean_a"] >= 0
    s = scan_command(hierarchy_spec(3), "institution.supervision_budget.lead",
                     [0, 3], metric="throughput", reps=1)
    assert len(s["metric_values"]) == 2


def test_protocol_report_command(tmp_path):
    from slime_mold.protocol import report_command

    out_dir = str(tmp_path / "bundle")
    res = report_command({"sim": {"turns": 5, "seed": 1},
                          "organization": {"roles": [
                              {"id": "a", "capabilities": ["t"]}],
                              "reporting": {"a": None}},
                          "taskflow": {"arrival_rate": 0.5,
                                       "task_types": ["t"]}},
                         out_dir)
    assert res["status"] == "ok"
    import os
    assert os.path.exists(os.path.join(out_dir, "ODD.txt"))
    assert os.path.exists(os.path.join(out_dir, "spec.yaml"))
    assert os.path.exists(os.path.join(out_dir, "reproduce.py"))


def test_protocol_cli_run(tmp_path):
    from slime_mold.protocol import main

    out = tmp_path / "out.json"
    rc = main(["run", "--spec", "demos/cs_flat.yaml", "--out", str(out),
               "--seed", "3", "--turns", "5"])
    assert rc == 0
    data = json.loads(out.read_text())
    assert data["config"]["seed"] == 3


def test_protocol_cli_compare(tmp_path):
    from slime_mold.protocol import main

    out = tmp_path / "cmp.json"
    rc = main(["compare", "--spec-a", "demos/cs_hierarchy.yaml",
               "--spec-b", "demos/cs_flat.yaml", "--metric", "success_rate",
               "--reps", "2", "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text())
    assert "statistics" in data


def test_protocol_cli_scan(tmp_path):
    from slime_mold.protocol import main

    out = tmp_path / "scan.json"
    rc = main(["scan", "--spec", "demos/cs_hierarchy.yaml",
               "--param", "institution.supervision_budget.lead",
               "--values", "0,3", "--metric", "throughput", "--reps", "1",
               "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text())
    assert len(data["metric_values"]) == 2


def test_protocol_cli_report(tmp_path):
    from slime_mold.protocol import main

    out_dir = tmp_path / "bundle2"
    rc = main(["report", "--spec", "demos/cs_hierarchy.yaml",
               "--out-dir", str(out_dir)])
    assert rc == 0
    assert (out_dir / "ODD.txt").exists()


def test_server_health_and_simulate():
    from slime_mold.server import make_server

    srv = make_server("127.0.0.1", 0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        import urllib.request

        h = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health")
        assert json.loads(h.read())["status"] == "ok"

        spec = {
            "sim": {"turns": 10, "seed": 1},
            "organization": {"roles": [{"id": "a", "capabilities": ["t"]}],
                             "reporting": {"a": None}},
            "taskflow": {"arrival_rate": 0.5, "task_types": ["t"]},
        }
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/simulate",
            data=json.dumps({"spec": spec}).encode(),
            headers={"Content-Type": "application/json"},
        )
        out = json.loads(urllib.request.urlopen(req).read())
        assert "metrics" in out

        ex = json.dumps({
            "mode": "compare",
            "spec_a": spec,
            "spec_b": dict(spec, name="b"),
            "reps": 1,
        }).encode()
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/experiment", data=ex,
            headers={"Content-Type": "application/json"})
        assert "statistics" in json.loads(urllib.request.urlopen(req2).read())

        bad = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/experiment",
            data=json.dumps({"mode": "nope"}).encode(),
            headers={"Content-Type": "application/json"})
        import urllib.error
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(bad)

        notfound = None
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/zzz")
        except urllib.error.HTTPError as exc:
            notfound = exc.code
        assert notfound == 404

        ex_spec = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/spec/example")
        assert isinstance(json.loads(ex_spec.read()), dict)

        options = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/simulate", method="OPTIONS")
        assert urllib.request.urlopen(options).status == 204
    finally:
        srv.shutdown()


def test_server_scan_and_report_endpoints():
    from slime_mold.server import make_server

    srv = make_server("127.0.0.1", 0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        import urllib.error
        import urllib.request

        spec = {
            "sim": {"turns": 8, "seed": 1},
            "organization": {"roles": [{"id": "a", "capabilities": ["t"]}],
                             "reporting": {"a": None}},
            "taskflow": {"arrival_rate": 0.5, "task_types": ["t"]},
        }

        scan_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/experiment",
            data=json.dumps({
                "mode": "scan",
                "spec": spec,
                "parameter": "taskflow.arrival_rate",
                "values": [0.2, 0.5],
                "metric": "throughput",
                "reps": 1,
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        scan = json.loads(urllib.request.urlopen(scan_req).read())
        assert scan["mode"] == "scan"
        assert len(scan["metric_values"]) == 2

        report_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/report",
            data=json.dumps({"spec": spec, "seed": 42, "note": "t"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        report = json.loads(urllib.request.urlopen(report_req).read())
        assert "ODD Protocol Description" in report["odd"]
        assert report["engine_version"]

        bad_spec = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/simulate",
            data=json.dumps({"spec": "not-a-dict"}).encode(),
            headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(bad_spec)

        bad_rep = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/report",
            data=json.dumps({"spec": []}).encode(),
            headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(bad_rep)
    finally:
        srv.shutdown()


def test_version_string():
    assert isinstance(__version__, str)
    assert "." in __version__
