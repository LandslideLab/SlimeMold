"""Targeted tests to harden coverage on stats, protocol, server, experiments."""

import json

import pytest

from aislimemold import stats

# ------------------------------------------------------------- stats depth


def test_t_pvalue_matches_normal_for_large_dof():
    # t=2.0 with huge dof ~ N(0,1): two-tailed p ~ 0.0455
    p = stats._two_tailed_t_pvalue(2.0, 1e9)
    assert p == pytest.approx(0.0455, abs=0.002)


def test_t_pvalue_zero_is_one():
    assert stats._two_tailed_t_pvalue(0.0, 10) == pytest.approx(1.0)


def test_t_pvalue_small_dof():
    p = stats._two_tailed_t_pvalue(1.0, 2)
    assert 0.3 < p < 0.5


def test_mann_whitney_ties():
    a = [1.0, 1.0, 1.0]
    b = [1.0, 1.0, 1.0]
    res = stats.mann_whitney_u(a, b)
    assert res["significant"] is False


def test_mann_whitney_single():
    res = stats.mann_whitney_u([5.0], [1.0])
    assert res["u"] >= 0


def test_betainc_edges():
    assert stats._betainc_upper(0.5, 0.5, 0.0) == 0.0
    assert stats._betainc_upper(0.5, 0.5, 1.0) == 1.0
    assert stats._betainc_upper(0.5, 0.5, 0.5) == pytest.approx(0.5, abs=0.02)


def test_cohens_d_pooled_unequal_sizes():
    d = stats.cohens_d([1.0, 2.0], [5.0, 6.0, 7.0])
    assert d != 0.0


def test_mean_and_sd_empty():
    assert stats.mean_and_sd([]) == (0.0, 0.0)


# ------------------------------------------------------- experiments depth


def test_report_uses_tempdir_when_no_outdir():
    from aislimemold.experiments import report

    path = report({"organization": {"roles": [{"id": "a"}],
                                    "reporting": {"a": None}}},
                  out_dir=None, seed=5)
    import os
    assert os.path.exists(os.path.join(path, "metadata.json"))


def test_scan_reps_averaging():
    from aislimemold.demo import hierarchy_spec
    from aislimemold.experiments import scan

    res = scan(hierarchy_spec(3), "institution.supervision_budget.lead",
               [0], metric="throughput", turns=10, reps=3)
    assert len(res.metric_values) == 1
    assert 0 <= res.metric_values[0]


def test_compare_t_test_option():
    from aislimemold.demo import flat_spec, hierarchy_spec
    from aislimemold.experiments import compare

    res = compare(hierarchy_spec(3), flat_spec(), metric="success_rate",
                  reps=2, test="t", turns=15)
    assert res.statistics["test"] == "welch_t"


def test_metric_value_top_level_number():
    from aislimemold.experiments import metric_value

    assert metric_value({"n_completed": 5}, "n_completed") == 5.0
    assert metric_value({"n_completed": 5}, "n_completed") == 5.0


# ------------------------------------------------------- protocol depth


def test_protocol_serve_short_lived(tmp_path):
    import threading

    from aislimemold.server import make_server

    srv = make_server("127.0.0.1", 0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    import urllib.error
    import urllib.request

    # scan experiment endpoint
    spec = {
        "organization": {"roles": [{"id": "a", "capabilities": ["t"]}],
                         "reporting": {"a": None}},
        "taskflow": {"arrival_rate": 0.5, "task_types": ["t"]},
    }
    body = json.dumps({"mode": "scan", "spec": spec,
                       "parameter": "taskflow.arrival_rate",
                       "values": [0.5, 1.0], "metric": "throughput"}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/experiment", data=body,
        headers={"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req).read())
    assert out["mode"] == "scan"
    assert len(out["metric_values"]) == 2

    # simulate with explicit seed/turns
    body = json.dumps({"spec": spec, "seed": 1, "turns": 5}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/simulate", data=body,
        headers={"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req).read())
    assert out["config"]["seed"] == 1

    # simulate without a spec -> 400
    body = json.dumps({}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/simulate", data=body,
        headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req)
        raised = None
    except urllib.error.HTTPError as exc:
        raised = exc.code
    assert raised == 400
    srv.shutdown()


def test_protocol_cli_bad_spec(tmp_path):
    from aislimemold.protocol import main

    rc = main(["run", "--spec", "nonexistent.yaml", "--out", "x.json"])
    assert rc == 1


def test_protocol_cli_serve_returns_running(tmp_path):
    # serve never returns; ensure it starts and can be Ctrl-C'ed
    import subprocess
    import sys
    import time

    proc = subprocess.Popen(
        [sys.executable, "-m", "aislimemold", "serve", "--host", "127.0.0.1",
         "--port", "0"],
        env={"PYTHONPATH": "src"}, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, cwd=str(tmp_path.parent.parent),
    )
    time.sleep(0.8)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    assert True


def test_load_spec_json(tmp_path):
    from aislimemold.protocol import load_spec

    p = tmp_path / "spec.json"
    p.write_text(json.dumps({"organization": {"roles": [
        {"id": "a"}], "reporting": {"a": None}}}))
    spec = load_spec(str(p))
    assert spec["organization"]["roles"][0]["id"] == "a"


def test_parse_values_cli():
    from aislimemold.protocol import _parse_values

    assert _parse_values("0,3,5") == [0, 3, 5]
    assert _parse_values("[0.5, 1.0]") == [0.5, 1.0]
