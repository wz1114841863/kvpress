"""Validation rules for the RTL3.1 testbench-only functional memory environment."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


VERSION = "kvzap-route-a-rtl3-1-functional-memory-environment-1.0"
STATUS = "complete_testbench_only_functional_memory_environment"
OWNER = "testbench_route_a_functional_memory_environment"
STOP_SCOPE = (
    "packed_read_association_owner blocks rtl3_2",
    "partial_provider_query_position_contract blocks rtl3_5",
)


class RTL31FunctionalMemoryEnvironmentError(ValueError):
    """Raised when RTL3.1 grows beyond its testbench functional boundary."""


def load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL31FunctionalMemoryEnvironmentError("RTL3.1 manifest root must be an object")
    return value


def validate(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != VERSION or manifest.get("status") != STATUS:
        raise RTL31FunctionalMemoryEnvironmentError("unexpected RTL3.1 version or status")
    if manifest.get("owner") != OWNER or manifest.get("interface") != "existing core_mem_if_v1 external init/request/response interface":
        raise RTL31FunctionalMemoryEnvironmentError("RTL3.1 must remain at the existing external R1 interface")
    scope = str(manifest.get("scope", ""))
    if not all(token in scope for token in ("Host-side", "not production Chisel RTL")):
        raise RTL31FunctionalMemoryEnvironmentError("RTL3.1 testbench-only scope missing")
    rules = manifest.get("transaction_rules")
    if not isinstance(rules, Mapping) or set(rules) != {"init", "request_backpressure", "read", "write", "response_backpressure", "reset"}:
        raise RTL31FunctionalMemoryEnvironmentError("RTL3.1 transaction-rule inventory drift")
    if "materialize only on accepted successful terminal" not in str(rules["write"]):
        raise RTL31FunctionalMemoryEnvironmentError("write durability boundary drift")
    fixture = manifest.get("fixture_object")
    if not isinstance(fixture, Mapping) or fixture.get("key") != "explicit address_ref":
        raise RTL31FunctionalMemoryEnvironmentError("functional fixture identity drift")
    if "not inferred" not in str(fixture.get("limit", "")):
        raise RTL31FunctionalMemoryEnvironmentError("functional metadata must not be inferred")
    if tuple(manifest.get("scoreboard_observations", [])) != ("request_accept", "fragment_deliver", "write_commit"):
        raise RTL31FunctionalMemoryEnvironmentError("RTL3.1 scoreboard observation drift")
    if tuple(manifest.get("unresolved_stops", [])) != STOP_SCOPE:
        raise RTL31FunctionalMemoryEnvironmentError("RTL3.1 cannot clear unrelated RTL3.0 stops")
    forbidden = set(manifest.get("forbidden", []))
    required_forbidden = {
        "production-top binding claim", "HBM controller claim", "latency bandwidth throughput or PPA claim",
        "payload metadata or residency authority transfer", "S2 association or sidecar publication",
        "scheduler admission pruning or atomic-publication change", "new A4 DSE", "Full-KV fallback",
    }
    if not required_forbidden <= forbidden:
        raise RTL31FunctionalMemoryEnvironmentError("RTL3.1 evidence boundary drift")


def validate_hashes(manifest: Mapping[str, Any], root: str | Path) -> None:
    base = Path(root).resolve()
    hashes = manifest.get("source_sha256")
    if not isinstance(hashes, Mapping) or not hashes:
        raise RTL31FunctionalMemoryEnvironmentError("RTL3.1 must hash-bind sources")
    for relative, expected in hashes.items():
        path = (base / str(relative)).resolve()
        if base not in path.parents or not path.is_file() or not isinstance(expected, str) or len(expected) != 64:
            raise RTL31FunctionalMemoryEnvironmentError("invalid RTL3.1 source hash")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RTL31FunctionalMemoryEnvironmentError(f"hash-bound source drift: {relative}")


def load_and_validate(manifest_path: str | Path, root: str | Path) -> None:
    manifest = load(manifest_path)
    validate(manifest)
    validate_hashes(manifest, root)
