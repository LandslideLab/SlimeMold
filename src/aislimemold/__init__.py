"""SlimeMold: an agent-based testbed for human + AI agent organization design.

SlimeMold models organizations (roles, reporting topology, institutions,
knowledge, task flows and turnover) as a deterministic, turn-based agent-based
simulation. It is a vertical "organization management" layer on top of the
standard ABM toolchain: everything is expressed in organizational constructs
span-of-control, delegation/supervision, autonomy, coordination cost, learning
and resilience and talks back to management theories (contingency, agency,
organizational learning, coordination theory).

The engine has no runtime dependencies: it runs on the Python standard library
(Python 3.11+), which keeps simulations fully reproducible and allows the
engine to be embedded anywhere (CI, notebooks, web workers via Pyodide).
"""

from . import autonomy, dsl, experiments, metrics, organization, simulation
from .__version__ import __version__
from .organization import Organization, OrgRole
from .simulation import SimConfig, SimulationResult, SimulationRunner

__all__ = [
    "OrgRole",
    "Organization",
    "SimConfig",
    "SimulationResult",
    "SimulationRunner",
    "__version__",
    "autonomy",
    "dsl",
    "experiments",
    "metrics",
    "organization",
    "simulation",
]
