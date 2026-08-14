"""Tests for roles and organization topology."""

import pytest

from slime_mold.organization import Organization, TopologyError
from slime_mold.roles import Member, OrgRole, describe_topology, iter_roles


def make_roles():
    return [
        OrgRole(id="root", capabilities={"x"}, autonomy="approver"),
        OrgRole(id="mid", capabilities={"y"}),
        OrgRole(id="leaf", capabilities={"z"}),
    ]


def test_orgrole_defaults():
    r = OrgRole(id="r", capabilities=["a"])
    assert r.name == ""
    assert r.can_handle == frozenset({"a"})


def test_orgrole_mandate_restricts():
    r = OrgRole(id="r", capabilities={"a", "b"}, mandate={"a"})
    assert r.can_handle == frozenset({"a"})


def test_orgrole_roundtrip_dict():
    r = OrgRole(id="r", name="R", capabilities={"a"}, autonomy="consultant",
                responsibilities=["res"], mandate={"a"})
    d = r.to_dict()
    r2 = OrgRole.from_dict(d)
    assert r2 == r


def test_orgrole_empty_id_rejected():
    with pytest.raises(ValueError):
        OrgRole(id="")


def test_hierarchy_topology():
    org = Organization.from_spec(make_roles(), {"mid": "root", "leaf": "mid"})
    assert org.shape() == "hierarchy"
    assert org.max_depth() == 2
    assert org.span_of_control("root") == 1
    assert org.span_of_control("mid") == 1
    assert org.direct_reports("root") == ["mid"]
    assert org.subordinates("root") == ["mid", "leaf"]
    assert org.ancestors("leaf") == ["mid", "root"]
    assert org.roots() == ["root"]
    assert org.leaves() == ["leaf"]


def test_flat_topology():
    org = Organization.from_spec(make_roles(), {"mid": None, "leaf": None,
                                                "root": None})
    assert org.shape() == "flat"
    assert org.max_depth() == 0
    assert org.max_span() == 0


def test_matrix_topology():
    org = Organization.from_spec(make_roles(), {"mid": ["root", "root"],
                                                "leaf": "mid"})
    assert org.shape() == "matrix"
    assert org.managers("mid") == ["root", "root"]


def test_multiple_roots():
    org = Organization.from_spec(
        [OrgRole(id="a"), OrgRole(id="b")], {"a": None, "b": None}
    )
    assert org.shape() == "flat"


def test_cycle_detected():
    roles = [OrgRole(id="a"), OrgRole(id="b")]
    with pytest.raises(TopologyError, match="cycle"):
        Organization.from_spec(roles, {"a": "b", "b": "a"})


def test_unknown_manager():
    with pytest.raises(TopologyError):
        Organization.from_spec(make_roles(), {"mid": "ghost", "leaf": "mid",
                                              "root": None})


def test_missing_reporting_entry_defaults_to_root():
    org = Organization.from_spec(make_roles(), {"mid": "root", "leaf": "mid"})
    assert "root" in org.roots()
    assert org.depth_of("root") == 0


def test_disconnected_allowed():
    org = Organization.from_spec([OrgRole(id="a"), OrgRole(id="b")],
                                 {"a": None}, allow_disconnected=True)
    assert org.max_depth() == 0


def test_span_and_avg():
    roles = [OrgRole(id="r"), OrgRole(id="a"), OrgRole(id="b"),
             OrgRole(id="c")]
    org = Organization.from_spec(roles, {"a": "r", "b": "r", "c": "r"})
    assert org.span_of_control("r") == 3
    assert org.avg_span() == 3.0
    assert org.max_span() == 3


def test_to_dict_roundtrip():
    org = Organization.from_spec(make_roles(), {"mid": "root", "leaf": "mid"})
    d = org.to_dict()
    assert d["shape"] == "hierarchy"
    assert d["max_depth"] == 2
    assert set(d["roles"]) == {"root", "mid", "leaf"}


def test_summary_string():
    org = Organization.from_spec(make_roles(), {"mid": "root", "leaf": "mid"})
    assert "hierarchy" in org.summary()


def test_describe_topology():
    assert "a -> b" in describe_topology({"a": "b"})
    assert "a -> root" in describe_topology({"a": None})


def test_iter_roles_duplicate():
    with pytest.raises(ValueError):
        iter_roles([OrgRole(id="a"), OrgRole(id="a")])


def test_member_skill_gain():
    m = Member(id="m", role_id="r", experience=0.9)
    m.skill_gain()
    assert m.experience == pytest.approx(0.915)
    m2 = Member(id="m2", role_id="r")
    m2.skill_gain()
    assert m2.tenure == 1
    assert m2.experience == pytest.approx(0.515)
