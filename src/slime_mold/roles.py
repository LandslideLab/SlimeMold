"""Role and member models.

An :class:`OrgRole` is a *position* in the organization (id, name,
capabilities, responsibilities, autonomy baseline). A :class:`Member` is a
*human or AI agent* occupying the role at a point in time. Separating roles
from members is what makes turnover (people come and go) and staffing changes
first-class: the topology stays, the knowledge leaves with the member.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

from . import autonomy as _autonomy
from .autonomy import AutonomyLevel


@dataclasses.dataclass(frozen=True)
class OrgRole:
    """A position in the organization.

    Parameters
    ----------
    id:
        Unique role id (used as the reporting-topology key).
    name:
        Human readable name.
    capabilities:
        Set of capability tags the role is proficient in (e.g.
        ``{"tier1", "tier2", "billing"}``).
    responsibilities:
        Optional list of responsibility descriptions (informational).
    autonomy:
        Baseline autonomy level for the role.
    mandate:
        Optional dict mapping capability tags to allowed work types; defaults
        to any capability. Used by approval gates.
    """

    id: str
    name: str = ""
    capabilities: frozenset[str] = frozenset()
    responsibilities: tuple[str, ...] = ()
    autonomy: AutonomyLevel = AutonomyLevel.COLLABORATOR
    mandate: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("role id must be non-empty")
        if isinstance(self.autonomy, str):
            object.__setattr__(self, "autonomy", _autonomy.AutonomyLevel(self.autonomy))
        if not isinstance(self.capabilities, frozenset):
            object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        if not isinstance(self.mandate, frozenset):
            object.__setattr__(self, "mandate", frozenset(self.mandate))
        if not isinstance(self.responsibilities, tuple):
            object.__setattr__(self, "responsibilities", tuple(self.responsibilities))

    @property
    def can_handle(self) -> frozenset[str]:
        """Capabilities this role is allowed to execute tasks for."""
        return self.mandate or self.capabilities

    @classmethod
    def from_dict(cls, data: dict) -> OrgRole:
        kwargs = dict(data)
        kwargs["autonomy"] = AutonomyLevel(kwargs.get("autonomy", "collaborator"))
        kwargs["capabilities"] = frozenset(kwargs.get("capabilities", ()))
        kwargs["mandate"] = frozenset(kwargs.get("mandate", ()))
        kwargs["responsibilities"] = tuple(kwargs.get("responsibilities", ()))
        return cls(**kwargs)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self) | {
            "autonomy": self.autonomy.value,
            "capabilities": sorted(self.capabilities),
            "mandate": sorted(self.mandate),
            "responsibilities": list(self.responsibilities),
        }


@dataclasses.dataclass
class Member:
    """A concrete human or AI agent occupying a role.

    ``experience`` (0-1) is a proxy for on-the-job competence and, together
    with the knowledge mechanism, drives the member's error probability.
    ``tenure`` counts the turns the member has been in role.
    """

    id: str
    role_id: str
    kind: str = "scripted"  # "scripted" | "llm" | "human"
    experience: float = 0.5
    tenure: int = 0
    is_active: bool = True

    def skill_gain(self, amount: float = 0.015) -> None:
        """Increase on-the-job experience after successful work."""
        self.experience = min(1.0, self.experience + amount)
        self.tenure += 1


def describe_topology(reporting: dict[str, str | list[str]]) -> str:
    """Short human-readable summary of a reporting topology for logs/reports."""
    lines: list[str] = []
    for role, manager in reporting.items():
        if isinstance(manager, list):
            lines.append(f"{role} -> {','.join(manager)}")
        elif manager is None or manager == "":
            lines.append(f"{role} -> root")
        else:
            lines.append(f"{role} -> {manager}")
    return "; ".join(lines)


def iter_roles(roles: Iterable[OrgRole] | dict[str, OrgRole]) -> dict[str, OrgRole]:
    """Index an iterable (or id->role dict) of roles by id with duplicate detection."""
    index: dict[str, OrgRole] = {}
    for role in roles.values() if isinstance(roles, dict) else roles:
        if role.id in index:
            raise ValueError(f"duplicate role id: {role.id}")
        index[role.id] = role
    return index
