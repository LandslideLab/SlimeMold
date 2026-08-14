"""Tests for the customer-service demo."""


from slime_mold import demo
from slime_mold.dsl import build_spec


def test_demo_specs_build():
    h = build_spec(demo.hierarchy_spec(3))
    assert h.org.shape() == "hierarchy"
    assert h.org.max_depth() == 1
    assert h.org.span_of_control("lead") == 2
    f = build_spec(demo.flat_spec())
    assert f.org.shape() == "flat"


def test_demo_budget_variants():
    for budget in (0, 3, None):
        spec = demo.hierarchy_spec(budget)
        assert spec["institution"]["supervision_budget"]["lead"] == budget


def test_example_spec_servable():
    assert demo.EXAMPLE_SPEC["name"] == "customer-service-hierarchy"


def test_run_demo_returns_rows():
    rows = demo.run_demo(seed=42, turns=20, verbose=False)
    assert len(rows) >= 4  # hierarchy x3 budgets + flat
    assert rows[0]["design"] == "hierarchy"
    assert rows[0]["throughput"] >= 0


def test_render_demo_header():
    text = demo.render_demo(demo.run_demo(seed=1, turns=10, verbose=False))
    assert "thrpt" in text
    assert "hierarchy" in text
