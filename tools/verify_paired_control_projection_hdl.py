#!/usr/bin/env python3
"""Verify generated paired control-projection HDL without invoking DC.

This is deliberately a structural pre-DC check: it confirms emitted top names,
typed external boundary tokens, and exclusion of the retired composition/test
reference modules. It does not prove synthesis preservation or PPA.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path


EXPECTATIONS = {
    "full_kv_control_projection": {
        "file": "full_kv_control_projection.sv",
        "required": [
            "full_kv_read_work_in_valid",
            "external_core_mem_if_v1_request_valid",
            "full_kv_payload_read_req_in_valid",
            "full_kv_payload_read_rsp_out_valid",
            "full_kv_consumer_commit_in_valid",
            "attention_terminal_rsp_valid",
            "runtime_retire_req_valid",
            "session_retire_ack_valid",
        ],
        "forbidden_modules": ["route_a_kv_subsystem_top"],
    },
    "route_a_control_projection": {
        "file": "route_a_control_projection.sv",
        "required": [
            "external_core_mem_if_v1_request_valid",
            "functional_sidecar_work_out_valid",
            "functional_sidecar_payload_release_out_valid",
            "functional_sidecar_registry_allocate_in_valid",
            "functional_sidecar_read_issue_in_valid",
            "functional_partial_hot_offer_in_valid",
            "functional_partial_pending_offer_in_valid",
            "functional_partial_packed_offer_in_valid",
            "functional_r4_accepted_packet_out_valid",
            "functional_r4_merge_work_out_valid",
            "functional_r4_result_in_valid",
            "functional_r4_numeric_fault_in_valid",
            "attention_terminal_rsp_valid",
            "session_retire_ack_valid",
        ],
        "forbidden_modules": [
            "route_a_kv_subsystem_top",
            "route_a_functional_sidecar_delivery_adapter",
            "route_a_functional_partial_provider_boundary",
            "route_a_functional_r4_reference_boundary",
        ],
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory", type=Path)
    parser.add_argument(
        "--route-a-split-directory",
        type=Path,
        help="directory containing the split-Verilog Route-A compilation unit",
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    report = {"schema_version": "paired-control-projection-hdl-check-v1", "tops": {}}
    failure = False
    for top, expectation in EXPECTATIONS.items():
        split_directory = (
            args.route_a_split_directory if top == "route_a_control_projection" else None
        )
        directory = split_directory or args.output_directory
        path = directory / expectation["file"]
        # The Route-A split compilation unit deliberately contains nested
        # verification support modules.  Full-KV is one independent flat
        # compilation unit and must not accidentally absorb Route-A children
        # merely because both artifacts share a parent directory.
        if directory.exists():
            sv_files = (
                sorted(directory.rglob("*.sv"))
                if split_directory is not None
                else sorted(directory.glob("*.sv"))
            )
        else:
            sv_files = []
        text = "\n".join(
            candidate.read_text(encoding="utf-8") for candidate in sv_files
        )
        missing = [token for token in expectation["required"] if token not in text]
        forbidden = [
            token for token in expectation["forbidden_modules"] if f"module {token}" in text
        ]
        filelist = directory / f"{top}.f"
        expected_filelist = "".join(
            f"{candidate.relative_to(directory).as_posix()}\n" for candidate in sv_files
        )
        filelist_ok = filelist.exists() and filelist.read_text(encoding="utf-8") == expected_filelist
        result = {
            "systemverilog": expectation["file"],
            "exists": path.exists(),
            "sha256": sha256(path) if path.exists() else None,
            "bytes": path.stat().st_size if path.exists() else 0,
            "compilation_unit_directory": str(directory),
            "systemverilog_file_count": len(sv_files),
            "compilation_unit_sha256": {
                candidate.relative_to(directory).as_posix(): sha256(candidate) for candidate in sv_files
            },
            "top_module_present": bool(re.search(rf"^module {re.escape(top)}(?:\s|\(|$)", text, re.MULTILINE)),
            "missing_required_tokens": missing,
            "forbidden_modules_present": forbidden,
            "filelist_exact": filelist_ok,
        }
        result["pass"] = (
            result["exists"]
            and result["top_module_present"]
            and not missing
            and not forbidden
            and filelist_ok
        )
        report["tops"][top] = result
        failure |= not result["pass"]

    manifest = args.output_directory / "paired_control_projection_emission_manifest.json"
    report["emission_manifest_exists"] = manifest.exists()
    # A direct firtool split flow has a separate provenance record from the
    # Scala single-unit emitter. The final package manifest records both; an
    # older emitter-local manifest is informative, not a pass prerequisite.
    report["pass"] = not failure
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
