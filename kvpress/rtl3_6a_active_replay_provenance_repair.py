"""No-model validator for RTL3.6-A active replay provenance repair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


VERSION = "kvzap-route-a-rtl3-6a-active-replay-provenance-repair-1.0"
STATUS = "completed_active_replay_provenance_repair"
ACTIVE_BINDINGS = (
    "analysis/rtl2_4_3_attention_terminal_scoreboard_binding.json",
    "analysis/rtl2_5_5_active_state_scoreboard_binding.json",
)


class RTL36AProvenanceRepairError(ValueError):
    """The repair broadens historical event semantics or leaves active drift."""


def load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL36AProvenanceRepairError("RTL3.6-A manifest root must be an object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(manifest: Mapping[str, Any], root: str | Path) -> None:
    if manifest.get("schema_version") != VERSION or manifest.get("status") != STATUS:
        raise RTL36AProvenanceRepairError("unexpected RTL3.6-A version/status")
    if tuple(manifest.get("active_bindings", ())) != ACTIVE_BINDINGS:
        raise RTL36AProvenanceRepairError("active binding inventory drift")
    expected_audit = {
        ACTIVE_BINDINGS[0]: {
            "semantic_contract_changed": False,
            "revalidated_chisel_suites": 3,
            "stale_source_records_repaired": 5,
        },
        ACTIVE_BINDINGS[1]: {
            "semantic_contract_changed": False,
            "revalidated_chisel_suites": 3,
            "stale_source_records_repaired": 5,
        },
    }
    if manifest.get("audit") != expected_audit:
        raise RTL36AProvenanceRepairError("RTL3.6-A audit inventory or scope drift")
    disposition = manifest.get("disposition")
    if disposition != {
        "active_replay_provenance_repaired": True,
        "rtl3_functional_realization_complete": False,
        "next_required_closure": "rtl3_6b_same_instance_live_functional_provider_terminal_composition",
    }:
        raise RTL36AProvenanceRepairError("RTL3.6-A disposition must preserve functional no-PASS")
    forbidden = set(manifest.get("forbidden", ()))
    if not {
        "event schema owner carrier or field change",
        "production-top activation",
        "live Python Chisel co-simulation",
        "numeric memory timing or PPA claim",
        "new A4 DSE",
    } <= forbidden:
        raise RTL36AProvenanceRepairError("RTL3.6-A forbidden scope drift")
    for relative in ACTIVE_BINDINGS:
        binding = load(Path(root) / relative)
        sources = binding.get("source_sha256")
        if not isinstance(sources, Mapping) or not sources:
            raise RTL36AProvenanceRepairError(f"active binding lacks source hashes: {relative}")
        for source, expected in sources.items():
            if _sha256(Path(root) / source) != expected:
                raise RTL36AProvenanceRepairError(f"active binding still has source drift: {relative}:{source}")


def validate_hashes(manifest: Mapping[str, Any], root: str | Path) -> None:
    base = Path(root).resolve()
    hashes = manifest.get("source_sha256")
    if not isinstance(hashes, Mapping) or not hashes:
        raise RTL36AProvenanceRepairError("RTL3.6-A must hash-bind its repair sources")
    for relative, expected in hashes.items():
        path = (base / str(relative)).resolve()
        if base not in path.parents or not path.is_file() or not isinstance(expected, str) or len(expected) != 64:
            raise RTL36AProvenanceRepairError("invalid RTL3.6-A source hash")
        if _sha256(path) != expected:
            raise RTL36AProvenanceRepairError(f"hash-bound source drift: {relative}")


def load_and_validate(manifest_path: str | Path, root: str | Path) -> None:
    manifest = load(manifest_path)
    validate(manifest, root)
    validate_hashes(manifest, root)
