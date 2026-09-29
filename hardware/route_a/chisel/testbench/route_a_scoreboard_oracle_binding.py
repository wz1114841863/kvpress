"""Declaration-only RTL1.0.b bridge to the frozen Python scoreboard oracles.

This module deliberately does not execute a model, a GPU workload, or an oracle
event. R1--R6 behavioral RTL does not yet emit observables to dispatch. It
loads the frozen one-to-one binding inventory so future testbench code can use
the exact oracle path and semantic entry-point labels without changing them.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class ScoreboardOracleBinding:
    """One immutable architecture assertion to Python-oracle association."""

    assertion_id: str
    rtl_owner: str
    oracle: str
    entry_points: tuple[str, ...]
    observe: str
    forbidden_adapter: str


class RouteAScoreboardOracleBindingRegistry:
    """Read-only registry; it performs no event translation or oracle dispatch."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        binding_path = repo_root / "hardware/route_a/chisel/src/test/resources/rtl1_0_verification_binding.json"
        binding_data = json.loads(binding_path.read_text(encoding="utf-8"))
        oracle_path = repo_root / binding_data["scoreboard_oracle_manifest"]
        oracle_data = json.loads(oracle_path.read_text(encoding="utf-8"))
        declared = {record["assertion_id"] for record in binding_data["bindings"]}
        observed = {record["assertion_id"] for record in oracle_data["bindings"]}
        if declared != observed:
            raise ValueError("RTL1.0.b binding inventory differs from frozen oracle manifest")
        self._bindings = {
            record["assertion_id"]: ScoreboardOracleBinding(
                assertion_id=record["assertion_id"],
                rtl_owner=record["rtl_owner"],
                oracle=record["oracle"],
                entry_points=tuple(record["entry_points"]),
                observe=record["observe"],
                forbidden_adapter=record["forbidden_adapter"],
            )
            for record in oracle_data["bindings"]
        }

    def binding_for(self, assertion_id: str) -> ScoreboardOracleBinding:
        """Return the frozen binding without invoking its Python oracle."""

        return self._bindings[assertion_id]

    def assertion_ids(self) -> frozenset[str]:
        """Return the complete, unique set of assertion IDs."""

        return frozenset(self._bindings)
