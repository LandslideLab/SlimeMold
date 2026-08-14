"""Tests for the DSL, YAML parser, experiments and ODD reports."""

import json

import pytest

from slime_mold.dsl import SpecError, build_spec, parse_yaml
from slime_mold.experiments import (
    compare,
    report,
    run_spec,
    scan,
    set_param,
)
from slime_mold.report import ODDReport, reproduction_bundle

# --------------------------------------------------------------- yamlmini


def test_parse_basic_yaml():
    doc = parse_yaml("a: 1\nb: two\nc: true\nd: null\ne: [1, 2]\nf: {x: 1}")
    assert doc["a"] == 1
    assert doc["b"] == "two"
    assert doc["c"] is True
    assert doc["d"] is None
    assert doc["e"] == [1, 2]
    assert doc["f"] == {"x": 1}


def test_parse_nested_lists():
    doc = parse_yaml(
        "roles:\n"
        "  - id: a\n"
        "    caps:\n"
        "      - x\n"
        "      - y\n"
        "  - id: b\n"
        "reporting:\n"
        "  a: b\n"
    )
    assert doc["roles"][0] == {"id": "a", "caps": ["x", "y"]}
    assert doc["roles"][1] == {"id": "b"}
    assert doc["reporting"] == {"a": "b"}


def test_parse_bare_dash():
    doc = parse_yaml(
        "items:\n"
        "  -\n"
        "    id: x\n"
        "    v: 2\n"
        "  - {id: y}\n"
    )
    assert doc["items"][0] == {"id": "x", "v": 2}
    assert doc["items"][1] == {"id": "y"}


def test_parse_quoted_strings():
    doc = parse_yaml("name: 'Team Lead'\npath: \"a b\"")
    assert doc["name"] == "Team Lead"
    assert doc["path"] == "a b"


def test_parse_comments():
    doc = parse_yaml("# top\nname: x # trailing\nother: 1 # comment")
    assert doc == {"name": "x", "other": 1}


def test_parse_scalars():
    assert parse_yaml("v: 3.14\nw: -5\nz: yes\nn: no") == {
        "v": 3.14, "w": -5, "z": True, "n": False}


def test_parse_mixed_block_raises():
    with pytest.raises(ValueError):
        parse_yaml("a:\n  - 1\n  b: 2\n")


def test_parse_invalid_line_raises():
    with pytest.raises(ValueError):
        parse_yaml("a: 1\nnotvalid\n")


def test_parse_bad_indent():
    with pytest.raises(ValueError):
        parse_yaml("a:\n    b: 1\n  c: 2\n")


def test_parse_empty():
    assert parse_yaml("") is None
    assert parse_yaml("# just a comment") is None


def test_parse_inline_split_nested():
    doc = parse_yaml("a: [1, [2, 3], {k: v}]")
    assert doc["a"] == [1, [2, 3], {"k": "v"}]


# ------------------------------------------------------------------- dsl


def test_build_spec_from_dict(hierarchy_spec_dict):
    b = build_spec(hierarchy_spec_dict)
    assert b.org.shape() == "hierarchy"
    assert b.sim.seed == 7
    assert b.institution.supervision_budget["mgr"] == 5


def test_build_spec_from_yaml_string():
    b = build_spec(
        "name: x\nsim: {turns: 5}\n"
        "organization:\n  roles:\n    - {id: a, capabilities: [t]}\n"
        "  reporting: {a: null}\n"
        "taskflow: {arrival_rate: 1.0, task_types: [t]}\n"
    )
    assert b.org.shape() == "flat"


def test_build_spec_from_bytes():
    b = build_spec(
        b"organization:\n  roles:\n    - {id: a, capabilities: [t]}\n"
        b"  reporting: {a: null}\n"
    )
    assert len(b.org.roles) == 1


def test_build_spec_roles_as_dict():
    b = build_spec({
        "organization": {
            "roles": {"a": {"capabilities": ["t"]}},
            "reporting": {"a": None},
        }
    })
    assert b.org.roles["a"].id == "a"


def test_spec_error_missing_organization():
    with pytest.raises(SpecError):
        build_spec({"name": "x"})


def test_spec_error_agent_unknown_role():
    with pytest.raises(SpecError):
        build_spec({
            "organization": {"roles": [{"id": "a", "capabilities": ["t"]}],
                             "reporting": {"a": None}},
            "agents": [{"role": "ghost"}],
        })


def test_spec_error_bad_topology():
    with pytest.raises(SpecError):
        build_spec({
            "organization": {"roles": [{"id": "a"}, {"id": "b"}],
                             "reporting": {"a": "b", "b": "a"}},
        })


def test_spec_error_top_level_not_mapping():
    with pytest.raises(SpecError):
        build_spec([1, 2, 3])


def test_agents_overrides():
    b = build_spec({
        "organization": {"roles": [{"id": "a", "capabilities": ["t"]}],
                         "reporting": {"a": None}},
        "agents": [{"role": "a", "error_probability": 0.9}],
    })
    assert b.policy_overrides["a"].error_probability == 0.9


# ----------------------------------------------------------- experiments


def test_compare_basic():
    from slime_mold.demo import flat_spec, hierarchy_spec

    res = compare(hierarchy_spec(3), flat_spec(), metric="throughput",
                  reps=3, turns=30)
    assert len(res.values_a) == 3
    assert res.statistics["significant"] in (True, False)
    d = res.to_dict()
    assert d["mode"] == "compare"
    assert "spec_a" in d


def test_compare_bad_metric():
    from slime_mold.demo import flat_spec, hierarchy_spec

    with pytest.raises(KeyError):
        compare(hierarchy_spec(3), flat_spec(), metric="nope", reps=1,
                turns=5)


def test_scan_basic():
    from slime_mold.demo import hierarchy_spec

    res = scan(hierarchy_spec(3),
               "institution.supervision_budget.lead", [0, 3],
               metric="throughput", turns=20, reps=1)
    assert len(res.metric_values) == 2
    assert res.parameter == "institution.supervision_budget.lead"


def test_set_param_nested_copy():
    spec = {"institution": {"supervision_budget": {"lead": 3}}}
    out = set_param(spec, ["institution", "supervision_budget", "lead"], 9)
    assert out["institution"]["supervision_budget"]["lead"] == 9
    assert spec["institution"]["supervision_budget"]["lead"] == 3  # untouched


def test_run_spec_helper():
    spec = {
        "sim": {"turns": 10, "seed": 2},
        "organization": {"roles": [{"id": "a", "capabilities": ["t"]}],
                         "reporting": {"a": None}},
        "taskflow": {"arrival_rate": 0.5, "task_types": ["t"]},
    }
    res = run_spec(spec, seed=2, turns=10)
    assert res.metrics["performance"]["n_completed"] >= 0


def test_build_runner_returns_seed():
    from slime_mold.experiments import build_runner

    spec = {
        "organization": {"roles": [{"id": "a", "capabilities": ["t"]}],
                         "reporting": {"a": None}},
    }
    runner, seed = build_runner(spec, 123)
    assert seed == 123
    assert runner.config.seed == 123


# -------------------------------------------------------------- ODD report


def test_odd_report_render():
    spec = {"name": "x",
            "organization": {"roles": [{"id": "a", "capabilities": ["t"]}],
                             "reporting": {"a": None}},
            "sim": {"turns": 10, "seed": 1},
            "institution": {"delegation_strategy": "full"},
            "taskflow": {"arrival_rate": 0.5, "task_types": ["t"]},
            "knowledge": {"revalidation_probability": 0.1},
            "turnover": {"per_turn_probability": 0.0}}
    rep = ODDReport(spec, seed=1)
    text = rep.render()
    assert "ODD Protocol Description" in text
    assert "1. Overview" in text
    assert "3. Details" in text
    d = rep.to_dict()
    assert d["engine_version"]
    assert d["seed"] == 1


def test_reproduction_bundle(tmp_path):
    spec = {"name": "x",
            "organization": {"roles": [{"id": "a", "capabilities": ["t"]}],
                             "reporting": {"a": None}},
            "sim": {"turns": 5, "seed": 3},
            "taskflow": {"arrival_rate": 0.5, "task_types": ["t"]}}
    out = tmp_path / "bundle"
    reproduction_bundle(spec, 3, str(out), note="hi")
    assert (out / "metadata.json").exists()
    meta = json.loads((out / "metadata.json").read_text())
    assert meta["seed"] == 3
    assert (out / "spec.yaml").exists()


def test_report_function(tmp_path):

    out = tmp_path / "r"
    path = report({"organization": {"roles": [{"id": "a"}],
                                    "reporting": {"a": None}}},
                  out_dir=str(out), seed=5)
    assert path == str(out)
    assert (out / "ODD.txt").exists()
