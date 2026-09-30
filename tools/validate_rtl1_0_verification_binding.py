#!/usr/bin/env python3
"""Validate RTL1.0.b attachment plus incremental owner assertion binding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


class VerificationBindingError(ValueError):
    """Raised when the read-only RTL1.0.b binding registry drifts."""


def _load(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise VerificationBindingError(f"{path} must contain a JSON object")
    return loaded


def validate(repo_root: Path, binding_path: Path) -> None:
    """Check binding identity/ownership; never elaborate RTL or execute an oracle."""

    binding = _load(binding_path)
    if binding.get("schema_version") != "kvzap-route-a-rtl1-0-verification-binding-1.1":
        raise VerificationBindingError("unexpected RTL1.0/RTL1.1 binding schema")
    matrix = _load(repo_root / str(binding["assertion_matrix"]))
    oracle = _load(repo_root / str(binding["scoreboard_oracle_manifest"]))
    matrix_records = {record["id"]: record for record in matrix["records"]}
    oracle_records = {record["assertion_id"]: record for record in oracle["bindings"]}
    records = binding.get("bindings")
    if not isinstance(records, list):
        raise VerificationBindingError("binding records must be a list")
    record_by_id = {record.get("assertion_id"): record for record in records if isinstance(record, dict)}
    if set(record_by_id) != set(matrix_records) or len(record_by_id) != len(records):
        raise VerificationBindingError("binding assertion inventory differs from matrix")
    if set(oracle_records) != set(matrix_records):
        raise VerificationBindingError("frozen oracle assertion inventory differs from matrix")

    skeleton_modules = binding.get("skeleton_modules")
    if not isinstance(skeleton_modules, list):
        raise VerificationBindingError("skeleton_modules must be a list")
    module_names = {record.get("module") for record in skeleton_modules if isinstance(record, dict)}
    if len(module_names) != len(skeleton_modules):
        raise VerificationBindingError("skeleton module inventory contains duplicates or malformed rows")
    for module in skeleton_modules:
        source = repo_root / str(module["source"])
        text = source.read_text(encoding="utf-8")
        if f'override def desiredName: String = "{module["module"]}"' not in text:
            raise VerificationBindingError(f"skeleton source does not expose module {module['module']}")

    for assertion_id, record in record_by_id.items():
        matrix_record = matrix_records[assertion_id]
        if record.get("rtl_owner") != matrix_record["rtl_owner"]:
            raise VerificationBindingError(f"owner drift for {assertion_id}")
        if record["rtl_owner"] not in module_names:
            raise VerificationBindingError(f"unknown skeleton owner for {assertion_id}")
        if oracle_records[assertion_id]["rtl_owner"] != record["rtl_owner"]:
            raise VerificationBindingError(f"oracle owner drift for {assertion_id}")
        expected_role = "dut_guarantee" if matrix_record["kind"] == "safety" else "environment_fairness_assumption"
        if record.get("environment_role") != expected_role:
            raise VerificationBindingError(f"environment-role drift for {assertion_id}")
        if record.get("scoreboard_observation_api") != "RouteAScoreboardOracleBindingRegistry":
            raise VerificationBindingError(f"scoreboard adapter drift for {assertion_id}")

    r1_bound = {
        "a_descriptor_unique_memory_path",
        "a_reset_stale_exclusion",
        "a_stale_response",
    }
    r2_bound = {"a_ready_low_nonmutation", "a_fifo_credit_losslessness"}
    r3_bound = {"a_metadata_publish_commit"}
    s2_bound = {"a_gqa_release"}
    r6_bound = {
        "a_numeric_fault_consumer",
        "a_global_retirement_membership",
        "a_exactly_one_terminal",
    }
    for assertion_id, record in record_by_id.items():
        status = record.get("sva_binding_status")
        if assertion_id in r1_bound | r2_bound | r3_bound | s2_bound | r6_bound:
            if status != "owner_chisel_assert_bound":
                raise VerificationBindingError(f"owner Chisel assertion binding missing for {assertion_id}")
        elif status not in {"owner_state_pending", "owner_event_pending"}:
            raise VerificationBindingError(f"unexpected non-R1 assertion binding for {assertion_id}")

    sva_path = repo_root / str(binding["sva_binding_source"])
    sva_text = sva_path.read_text(encoding="utf-8")
    if "bind route_a_kv_subsystem_top route_a_rtl1_0_assertion_binding_registry" not in sva_text:
        raise VerificationBindingError("SVA registry is not bound to the frozen top")
    for assertion_id in matrix_records:
        if f"assertion-id: {assertion_id}" not in sva_text:
            raise VerificationBindingError(f"SVA registry lacks marker for {assertion_id}")
    for assertion_id in r1_bound:
        if f"r1-chisel-assertion: {assertion_id}" not in sva_text:
            raise VerificationBindingError(f"SVA registry lacks RTL1.1 R1 binding marker for {assertion_id}")
    for assertion_id in r2_bound:
        if f"r2-chisel-assertion: {assertion_id}" not in sva_text:
            raise VerificationBindingError(f"SVA registry lacks RTL1.2 R2 binding marker for {assertion_id}")
    for assertion_id in r3_bound:
        if f"r3-chisel-assertion: {assertion_id}" not in sva_text:
            raise VerificationBindingError(f"SVA registry lacks RTL1.3 R3 binding marker for {assertion_id}")
    for assertion_id in s2_bound:
        if f"s2-chisel-assertion: {assertion_id}" not in sva_text:
            raise VerificationBindingError(f"SVA registry lacks RTL1.4 S2 binding marker for {assertion_id}")
    for assertion_id in r6_bound:
        if f"r6-chisel-assertion: {assertion_id}" not in sva_text:
            raise VerificationBindingError(f"SVA registry lacks RTL1.5 R6 binding marker for {assertion_id}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate RTL1.0.b matrix/SVA/oracle attachment plus RTL1.1/R2/R3/S2/R6 Chisel-assert bindings; no model, GPU, formal proof, timing, or PPA claim."
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."), help="Repository root (default: %(default)s).")
    parser.add_argument(
        "--binding-manifest",
        type=Path,
        default=Path("hardware/route_a/chisel/src/test/resources/rtl1_0_verification_binding.json"),
        help="RTL1.0/RTL1.1/RTL1.2 binding manifest relative to repo root (default: %(default)s).",
    )
    args = parser.parse_args()
    try:
        repo_root = args.repo_root.resolve()
        binding_path = args.binding_manifest if args.binding_manifest.is_absolute() else repo_root / args.binding_manifest
        validate(repo_root, binding_path)
    except (KeyError, OSError, TypeError, json.JSONDecodeError, VerificationBindingError) as error:
        raise SystemExit(f"RTL1.0.b verification binding failed: {error}") from error
    print(f"RTL1.0/RTL1.1/RTL1.2/RTL1.3/RTL1.4/RTL1.5 verification binding passed: {binding_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
