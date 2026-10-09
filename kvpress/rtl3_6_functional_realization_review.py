"""No-model RTL3.6 functional-realization completion review validator.

The review deliberately distinguishes completed owner/model slices from a
missing same-instance, live cross-language functional composition.  It makes
no production RTL, physical-memory, numeric-datapath, timing, or PPA claim.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


VERSION = "kvzap-route-a-rtl3-6-functional-realization-completion-review-1.0"
STATUS = "reviewed_incomplete_live_cross_language_functional_composition"

REQUIRED_PRIOR = {
    "analysis/rtl3_1_functional_memory_environment_manifest.json": "complete_testbench_only_functional_memory_environment",
    "analysis/rtl3_2_packed_read_functional_integration_manifest.json": "complete_testbench_composed_functional_packed_payload_path_with_explicit_sidecar_boundary",
    "analysis/rtl3_4b_functional_r4_provider_manifest.json": "implemented_functional_oracle_provider_pre_rtl3_5_partial_producer",
    "analysis/rtl3_5b_functional_attention_partial_provider_manifest.json": "implemented_pure_software_functional_partial_provider_pre_numeric_rtl",
    "analysis/rtl3_5c_cross_language_packet_binding_manifest.json": "implemented_static_cross_language_packet_binding_pre_production_top",
}

REQUIRED_GAPS = (
    "no_same_instance_live_functional_partial_to_r4_to_r6_terminal_binding",
    "no_same_instance_functional_r4_terminal_to_retire_reclaim_binding",
    "s2_sidecar_transport_remains_explicit_testbench_ingress",
    "no_full_path_reset_epoch_composition_witness",
    "active_terminal_and_reclaim_replay_provenance_hashes_stale",
)

REQUIRED_BLOCKED_PREFLIGHT = {
    "command": ".venv/bin/python -m pytest -q tests/test_rtl2_6_5c_event_capture_replay.py",
    "failure_class": "active_scoreboard_binding_hash_drift_before_event_replay",
    "bindings": [
        "analysis/rtl2_4_3_attention_terminal_scoreboard_binding.json",
        "analysis/rtl2_5_5_active_state_scoreboard_binding.json",
    ],
}


class RTL36FunctionalRealizationReviewError(ValueError):
    """The review either hides a remaining realization gap or drifts in scope."""


def load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL36FunctionalRealizationReviewError("RTL3.6 review root must be an object")
    return value


def validate(manifest: Mapping[str, Any], root: str | Path) -> None:
    if manifest.get("schema_version") != VERSION or manifest.get("status") != STATUS:
        raise RTL36FunctionalRealizationReviewError("unexpected RTL3.6 review version/status")
    base = Path(root)
    if manifest.get("reviewed_predecessors") != REQUIRED_PRIOR:
        raise RTL36FunctionalRealizationReviewError("RTL3.6 predecessor inventory/status drift")
    for relative, expected_status in REQUIRED_PRIOR.items():
        if load(base / relative).get("status") != expected_status:
            raise RTL36FunctionalRealizationReviewError(f"predecessor status differs: {relative}")
    if tuple(manifest.get("open_gaps", ())) != REQUIRED_GAPS:
        raise RTL36FunctionalRealizationReviewError("RTL3.6 must preserve every live-composition gap")
    if manifest.get("blocked_preflight") != REQUIRED_BLOCKED_PREFLIGHT:
        raise RTL36FunctionalRealizationReviewError("RTL3.6 blocked replay preflight drift")
    disposition = manifest.get("disposition")
    if disposition != {
        "rtl3_functional_realization_complete": False,
        "next_required_closure": "rtl3_6a_repair_active_replay_provenance_before_live_functional_composition",
    }:
        raise RTL36FunctionalRealizationReviewError("RTL3.6 may not claim a functional-realization pass")
    required_evidence = {
        "functional_memory_transaction_environment",
        "packed_payload_to_s2_with_explicit_sidecar_boundary",
        "functional_partial_and_r4_oracle_models",
        "static_cross_language_structural_packet_binding",
        "historical_accepted_carrier_replay_record_not_revalidated_due_stale_active_bindings",
    }
    if set(manifest.get("reviewed_evidence", ())) != required_evidence:
        raise RTL36FunctionalRealizationReviewError("RTL3.6 evidence inventory drift")
    forbidden = set(manifest.get("forbidden", ()))
    required_forbidden = {
        "production-top activation claim",
        "live Python Chisel co-simulation claim",
        "Chisel attention MAC or FP numeric RTL claim",
        "HBM SRAM controller or physical-memory claim",
        "timing throughput area energy or PPA claim",
        "model GPU or new A4 DSE claim",
    }
    if not required_forbidden <= forbidden:
        raise RTL36FunctionalRealizationReviewError("RTL3.6 evidence boundary drift")


def validate_hashes(manifest: Mapping[str, Any], root: str | Path) -> None:
    base = Path(root).resolve()
    hashes = manifest.get("source_sha256")
    if not isinstance(hashes, Mapping) or not hashes:
        raise RTL36FunctionalRealizationReviewError("RTL3.6 review must hash-bind sources")
    for relative, expected in hashes.items():
        path = (base / str(relative)).resolve()
        if base not in path.parents or not path.is_file() or not isinstance(expected, str) or len(expected) != 64:
            raise RTL36FunctionalRealizationReviewError("invalid RTL3.6 source hash")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RTL36FunctionalRealizationReviewError(f"hash-bound source drift: {relative}")


def load_and_validate(manifest_path: str | Path, root: str | Path) -> None:
    manifest = load(manifest_path)
    validate(manifest, root)
    validate_hashes(manifest, root)
