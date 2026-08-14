"""Organization: roles plus a reporting topology.

The reporting topology is the backbone of every organizational construct in
SlimeMold. It supports the three canonical shapes:

* **hierarchy** -- a tree: every role has exactly one manager.
* **flat** -- a degenerate tree: all roles report to a single root (or none).
* **matrix** -- a DAG: a role may report to more than one manager (e.g. a
  functional manager and a project lead).

Span-of-control (number of direct reports) and hierarchy depth are derived
automatically from the topology, which lets experiments scan those quantities
as independent design variables and lets the engine *validate* a design against
managerial constraints (e.g. an impossible span or an orphaned role).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from .roles import OrgRole, describe_topology, iter_roles


class TopologyError(ValueError):
    """Raised when a reporting topology violates organizational invariants."""


@dataclass
class Organization:
    """A set of roles connected by a reporting topology.

    ``reporting`` maps each role id to its manager id (or a *list* of manager
    ids for matrix structures). A role whose manager is ``None`` (or not listed
    as a key with an empty manager) is a root.

    Validation invariants:
      * every manager must itself be a defined role;
      * the graph must be acyclic (no role is its own ancestor);
      * every role must be reachable from a root (no orphaned components) --
        unless ``allow_disconnected`` is set for experiments on partial orgs.
    """

    name: str = "organization"
    roles: dict[str, OrgRole] = field(default_factory=dict)
    reporting: dict[str, str | list[str] | None] = field(default_factory=dict)
    allow_disconnected: bool = False

    # -- construction helpers -------------------------------------------------

    @classmethod
    def from_spec(
        cls,
        roles: Iterable[OrgRole] | dict[str, OrgRole],
        reporting: dict[str, str | list[str] | None],
        name: str = "organization",
        allow_disconnected: bool = False,
    ) -> Organization:
        index = iter_roles(roles)
        org = cls(
            name=name,
            roles=index,
            reporting=reporting,
            allow_disconnected=allow_disconnected,
        )
        org.validate()
        return org

    # -- topology queries -----------------------------------------------------

    def validate(self) -> None:
        """Validate structural invariants; raise :class:`TopologyError`."""
        for role_id in self.reporting:
            if role_id not in self.roles:
                raise TopologyError(f"reporting references unknown role: {role_id}")
        for role_id in self.roles:
            if role_id not in self.reporting:
                # a role with no reporting entry is a root
                self.reporting[role_id] = None

        # acyclicity + orphan detection via DFS from roots
        managers: dict[str, list[str]] = {}
        for role_id, mgr in self.reporting.items():
            if isinstance(mgr, list):
                managers[role_id] = list(mgr)
            elif mgr:
                managers[role_id] = [mgr]
            else:
                managers[role_id] = []

        state: dict[str, str] = {}
        roots: list[str] = []

        def dfs(node: str, path: list[str]) -> None:
            if state.get(node) == "visiting":
                cycle = path[path.index(node) :] + [node]
                raise TopologyError(f"reporting cycle detected: {' -> '.join(cycle)}")
            if state.get(node) == "done":
                return
            state[node] = "visiting"
            for mgr in managers[node]:
                if mgr not in self.roles:
                    raise TopologyError(f"manager {mgr} of {node} is not a role")
                dfs(mgr, path + [node])
            state[node] = "done"

        for node in self.roles:
            if not managers[node]:
                roots.append(node)
            if node not in state:
                dfs(node, [node])

        if not self.allow_disconnected:
            for node in self.roles:
                if node not in state:
                    raise TopologyError(f"role {node} is not connected to any root")

        self._managers = managers
        self._roots = roots

    def managers(self, role_id: str) -> list[str]:
        """Manager ids of a role (empty for roots)."""
        mgr = self.reporting.get(role_id)
        if isinstance(mgr, list):
            return list(mgr)
        return [mgr] if mgr else []

    def direct_reports(self, role_id: str) -> list[str]:
        """Direct reports of a role (empty for leaves)."""
        return [r for r, mgr in self.reporting.items() if role_id in self.managers(r)]

    def span_of_control(self, role_id: str) -> int:
        """Number of direct reports (span-of-control)."""
        return len(self.direct_reports(role_id))

    def depth_of(self, role_id: str) -> int:
        """Distance (in reporting edges) from the nearest root to a role."""
        distances = self._depth_map()
        return distances[role_id]

    def _depth_map(self) -> dict[str, int]:
        distances: dict[str, int] = {}
        queue = [(root, 0) for root in self._roots]
        visited: set[str] = set()
        while queue:
            node, d = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            distances[node] = min(distances.get(node, 10**9), d)
            for child in self.direct_reports(node):
                queue.append((child, d + 1))
        for role in self.roles:
            distances.setdefault(role, 10**9)
        return distances

    def roots(self) -> list[str]:
        """Root role ids (roles with no manager)."""
        return list(self._roots)

    def leaves(self) -> list[str]:
        """Role ids with no direct reports."""
        return [r for r in self.roles if not self.direct_reports(r)]

    def max_depth(self) -> int:
        """Deepest reporting chain length."""
        return max((self.depth_of(r) for r in self.roles), default=0)

    def max_span(self) -> int:
        """Largest span-of-control across roles."""
        return max((self.span_of_control(r) for r in self.roles), default=0)

    def avg_span(self) -> float:
        """Mean span-of-control across non-leaf roles."""
        spans = [self.span_of_control(r) for r in self.roles if self.direct_reports(r)]
        return sum(spans) / len(spans) if spans else 0.0

    def ancestors(self, role_id: str) -> list[str]:
        """All superior roles along the reporting chain (nearest first)."""
        chain: list[str] = []
        seen: set[str] = set()
        current: list[str] = list(self.managers(role_id))
        while current:
            nxt: list[str] = []
            for m in current:
                if m in seen:
                    continue
                seen.add(m)
                chain.append(m)
                nxt.extend(self.managers(m))
            current = nxt
        return chain

    def subordinates(self, role_id: str) -> list[str]:
        """All roles that (transitively) report to *role_id*."""
        result: list[str] = []
        stack = list(self.direct_reports(role_id))
        while stack:
            node = stack.pop()
            if node in result:
                continue
            result.append(node)
            stack.extend(self.direct_reports(node))
        return result

    def all_members_below(self, role_id: str) -> list[str]:
        """Subordinates plus the role itself."""
        return [role_id] + self.subordinates(role_id)

    def shape(self) -> str:
        """Classify topology shape: 'hierarchy', 'flat' or 'matrix'."""
        has_matrix = any(
            isinstance(mgr, list) and len(mgr) > 1 for mgr in self.reporting.values()
        )
        if has_matrix:
            return "matrix"
        if self.max_depth() == 0:
            return "flat"
        return "hierarchy"

    def to_dict(self) -> dict:
        reporting = {}
        for rid, mgr in self.reporting.items():
            if isinstance(mgr, list):
                reporting[rid] = list(mgr)
            elif mgr:
                reporting[rid] = mgr
            else:
                reporting[rid] = None
        return {
            "name": self.name,
            "roles": {rid: r.to_dict() for rid, r in self.roles.items()},
            "reporting": reporting,
            "shape": self.shape(),
            "max_depth": self.max_depth(),
            "max_span": self.max_span(),
            "avg_span": self.avg_span(),
        }

    def summary(self) -> str:
        return (
            f"{self.name} [{self.shape()}] roles={len(self.roles)} "
            f"depth={self.max_depth()} max_span={self.max_span()} "
            f"avg_span={self.avg_span():.1f}\n{describe_topology(self.reporting)}"
        )
