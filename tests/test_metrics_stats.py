"""Tests for the MetricsEngine and statistics helpers."""

import pytest

from aislimemold import stats


def test_metrics_categories_present(built_hierarchy):
    from aislimemold.simulation import SimulationRunner

    r = SimulationRunner(built_hierarchy.org, built_hierarchy.institution,
                         built_hierarchy.taskflow, built_hierarchy.turnover,
                         built_hierarchy.knowledge, built_hierarchy.sim)
    result = r.run()
    m = result.metrics
    for cat in ("performance", "coordination", "quality", "decision",
                "knowledge", "resilience"):
        assert cat in m


def test_learning_curve_shapes(built_flat):
    from aislimemold.simulation import SimulationRunner

    r = SimulationRunner(built_flat.org, built_flat.institution,
                         built_flat.taskflow, built_flat.turnover,
                         built_flat.knowledge, built_flat.sim)
    result = r.run()
    lc = result.metrics["knowledge"]["learning_curve"]
    assert len(lc["windows"]) == len(lc["success_by_window"]) == 4


def test_resilience_with_turnover():
    spec = {
        "sim": {"turns": 60, "seed": 5},
        "organization": {
            "roles": [{"id": "a1", "capabilities": ["t1"], "autonomy": "approver"}],
            "reporting": {"a1": None},
        },
        "turnover": {"schedule": {30: ["a1"]}},
        "taskflow": {"arrival_rate": 1.0, "task_types": ["t1"]},
    }
    from aislimemold.dsl import build_spec
    from aislimemold.simulation import SimulationRunner

    b = build_spec(spec)
    r = SimulationRunner(b.org, b.institution, b.taskflow, b.turnover,
                         b.knowledge, b.sim)
    result = r.run()
    res = result.metrics["resilience"]
    assert res["n_events"] == 1
    assert "mean_drop" in res


def test_resilience_no_events():
    spec = {
        "sim": {"turns": 20, "seed": 5},
        "organization": {
            "roles": [{"id": "a1", "capabilities": ["t1"], "autonomy": "approver"}],
            "reporting": {"a1": None},
        },
        "taskflow": {"arrival_rate": 1.0, "task_types": ["t1"]},
    }
    from aislimemold.dsl import build_spec
    from aislimemold.simulation import SimulationRunner

    b = build_spec(spec)
    r = SimulationRunner(b.org, b.institution, b.taskflow, b.turnover,
                         b.knowledge, b.sim)
    result = r.run()
    assert result.metrics["resilience"]["events"] == []


def test_metric_value_extraction():
    from aislimemold.experiments import metric_value

    m = {"performance": {"throughput": 12.5},
         "coordination": {"escalations": 3}}
    assert metric_value(m, "throughput") == 12.5
    assert metric_value(m, "escalations") == 3.0
    with pytest.raises(KeyError):
        metric_value(m, "nope")


# ------------------------------------------------------------- statistics


def test_mean_and_sd():
    m, s = stats.mean_and_sd([1, 2, 3, 4, 5])
    assert m == pytest.approx(3.0)
    assert s > 0


def test_welch_t_significant():
    a = [10.0] * 10
    b = [5.0] * 10
    res = stats.welch_t_test(a, b)
    assert res["significant"] is True


def test_welch_t_identical_not_significant():
    a = [1.0, 2.0, 3.0, 4.0]
    res = stats.welch_t_test(a, list(a))
    assert res["significant"] is False


def test_welch_t_small_samples():
    res = stats.welch_t_test([1.0], [2.0])
    assert res["significant"] is False


def test_mann_whitney_separated():
    a = [1.0] * 8
    b = [5.0] * 8
    res = stats.mann_whitney_u(a, b)
    assert res["significant"] is True


def test_mann_whitney_empty():
    res = stats.mann_whitney_u([], [1.0])
    assert res["significant"] is False


def test_cohens_d():
    d = stats.cohens_d([1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0])
    assert d != 0.0


def test_cohens_d_same():
    assert stats.cohens_d([1.0, 2.0], [1.0, 2.0]) == pytest.approx(0.0)


def test_significance_report_auto():
    rep = stats.significance_report([3.0] * 6, [8.0] * 6)
    assert "cohens_d" in rep
    assert rep["test"] == "mann_whitney_u"


def test_significance_report_t():
    rep = stats.significance_report([3.0] * 6, [8.0] * 6, test="t")
    assert rep["test"] == "welch_t"


def test_significance_report_bad_test():
    with pytest.raises(ValueError):
        stats.significance_report([1.0], [2.0], test="bogus")


def test_two_tailed_normal_pvalue():
    assert stats._two_tailed_normal_pvalue(1.96) == pytest.approx(0.05, abs=0.001)
