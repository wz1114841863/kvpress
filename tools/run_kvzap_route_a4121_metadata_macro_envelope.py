#!/usr/bin/env python3
"""A4.12.1 CACTI proxy envelope for three frozen metadata organizations."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4121-metadata-macro-envelope-1.0"
A4120_SCHEMA = "kvzap-route-a4120-metadata-interface-inventory-1.0"
A4120_SHA256 = "e5a7ad30b45be7acbda7c2b0b788fdfa4ee74553d6fc93bc9317dce0c4be3534"
ENTRY_BITS = 64
ENTRY_BYTES = ENTRY_BITS // 8
LAYER_COUNT = 36
CACTI_PROXY_NODE_UM = 0.032
CACTI_SOURCE_URL = "https://github.com/HewlettPackard/cacti.git"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.12.1 three-candidate metadata macro-area envelope using a public CACTI technology proxy; "
            "not a PDK, cycle, throughput, workload-energy, architecture, or RTL result."
        )
    )
    parser.add_argument("--a4120-report", type=Path, required=True)
    parser.add_argument("--cacti-binary", type=Path, required=True, help="Built CACTI binary from the stated public source checkout.")
    parser.add_argument("--cacti-source-dir", type=Path, required=True, help="CACTI checkout containing cache.cfg and .git provenance.")
    parser.add_argument("--technology-node-um", type=float, default=CACTI_PROXY_NODE_UM, help="Public CACTI proxy node only; never a target PDK declaration.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate A4.12.0 and CACTI provenance without creating output or executing CACTI.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def ceil_div(value: int, divisor: int) -> int:
    if value < 0 or divisor <= 0:
        raise ValueError("invalid capacity division")
    return (value + divisor - 1) // divisor


def cacti_minimum_bytes(value: int) -> int:
    """CACTI's small-RAM proxy is floored at 1 KiB; report the padding explicitly."""
    return max(1024, value)


def require_a4120(path: Path) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != A4120_SHA256:
        raise ValueError("A4.12.1 requires the self-contained A4.12.0 _02 report by exact SHA-256")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != A4120_SCHEMA or report.get("status") != "complete":
        raise ValueError("A4.12.0 input is incomplete or schema-incompatible")
    guards = report.get("semantic_guards", {})
    required = (
        "only_accepted_a491_a410_a4112b_and_c5_contents_are_bound",
        "ha8_wide_service_capability_not_relabelled_as_physical_sram_ports",
        "logical_queue_contract_not_relabelled_as_per_layer_physical_sram_provision",
        "payload_dependent_address_fields_remain_parameterized",
        "a412_does_not_reopen_execution_queue_scheduler_or_pruning_variants",
    )
    if any(guards.get(key) is not True for key in required):
        raise ValueError("A4.12.0 semantic guards are incomplete")
    return report


def cacti_provenance(binary: Path, source_dir: Path, node_um: float) -> dict[str, Any]:
    if not binary.is_file() or not binary.stat().st_mode & 0o111:
        raise FileNotFoundError(f"CACTI binary is absent or not executable: {binary}")
    template = source_dir / "cache.cfg"
    if not template.is_file() or not (source_dir / ".git").exists():
        raise FileNotFoundError("CACTI source directory lacks cache.cfg or Git provenance")
    if node_um != CACTI_PROXY_NODE_UM:
        raise ValueError("A4.12.1 fixes the only public proxy node to 0.032 um; a node sweep is not admitted")
    commit = subprocess.run(["git", "-C", str(source_dir), "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
    origin = subprocess.run(["git", "-C", str(source_dir), "config", "--get", "remote.origin.url"], text=True, capture_output=True).stdout.strip()
    if origin != CACTI_SOURCE_URL:
        raise ValueError("CACTI source origin differs from the pre-registered public repository")
    return {"source_url": origin, "source_commit": commit, "build_command": "make -j2", "template_filename": "cache.cfg", "template_sha256": sha256_file(template), "technology_proxy_node_um": node_um, "technology_boundary": "CACTI public 0.032-um model is an analytical technology proxy, not a foundry PDK, synthesized macro, target process, or signoff estimate."}


def candidate_templates(a4120: dict[str, Any]) -> list[dict[str, Any]]:
    inventory = a4120["interface_inventory"]
    service = inventory["frozen_service_requirement"]
    logical = inventory["logical_resource_contract"]
    entry = inventory["metadata_entry_accounting"]
    if service["bank_count"] != 8 or service["mapping"] != "head_affine_v1":
        raise ValueError("A4.12.0 service requirement changed")
    if entry["declared_word_padded_width_bits"] != {"head_control": 64, "span_owner": 64}:
        raise ValueError("A4.12.0 entry width changed")
    counts = entry["joint_safe_modeled_object_counts"]
    if counts != {"head_control": 225, "span_owner": 614}:
        raise ValueError("A4.12.0 modeled object counts changed")
    local = int(logical["local_queue_capacity_per_bank_transaction_groups"])
    shared = int(logical["shared_overflow_capacity_per_layer_transaction_groups"])
    staging = int(logical["staging_capacity_per_layer_transaction_groups"])
    banks = int(service["bank_count"])
    per_bank_all = cacti_minimum_bytes(ceil_div(sum(counts.values()), banks) * ENTRY_BYTES)
    per_bank_head = cacti_minimum_bytes(ceil_div(counts["head_control"], banks) * ENTRY_BYTES)
    per_bank_span = cacti_minimum_bytes(ceil_div(counts["span_owner"], banks) * ENTRY_BYTES)
    local_per_bank = cacti_minimum_bytes(local * ENTRY_BYTES)
    shared_staging_per_layer = cacti_minimum_bytes((shared + staging) * ENTRY_BYTES)
    queue_entries_per_layer = banks * local + shared + staging
    pooled_queue_per_bank = cacti_minimum_bytes(ceil_div(LAYER_COUNT * queue_entries_per_layer, banks) * ENTRY_BYTES)
    common = {"entry_bits": ENTRY_BITS, "bank_count": banks, "layer_count_assumption": LAYER_COUNT, "logical_contract_entries_per_layer": queue_entries_per_layer, "physical_provisioning_boundary": "The 36-layer mapping below is an explicit conservative physical-organization candidate, not evidence that all layers require independent simultaneous storage. A4.10 trace peaks are reported separately and do not prove a safe smaller pool."}
    return [
        {"name": "M1_banked_sram_pipelined_rmw", "organization": "Dedicated per-layer queue/staging macros plus one banked co-located persistent metadata macro; a two-phase RMW pipeline is a later A4.12.2 service hypothesis, not modeled by CACTI.", "macro_requests": [
            {"role": "persistent_head_control_and_span_owner", "instances": banks, "bytes_per_instance": per_bank_all},
            {"role": "local_queue_per_bank_per_layer", "instances": banks * LAYER_COUNT, "bytes_per_instance": local_per_bank},
            {"role": "shared_plus_staging_per_layer", "instances": LAYER_COUNT, "bytes_per_instance": shared_staging_per_layer},
        ], "non_cacti_state": [], **common},
        {"name": "M2_replicated_or_duplicated_control_storage", "organization": "Two banked head-control replicas, one banked span-owner store, and eight quota-accounted pooled queue shards. Replica coherence and the actual service schedule remain unmodeled until A4.12.2.", "macro_requests": [
            {"role": "replicated_head_control", "instances": 2 * banks, "bytes_per_instance": per_bank_head},
            {"role": "span_owner_primary", "instances": banks, "bytes_per_instance": per_bank_span},
            {"role": "quota_accounted_pooled_queue_staging_shard", "instances": banks, "bytes_per_instance": pooled_queue_per_bank},
        ], "non_cacti_state": [], **common},
        {"name": "M3_register_hot_state_with_sram_backing", "organization": "Per-bank head-control hot state is represented as registers; span-owner and quota-accounted pooled queue/staging remain CACTI SRAM proxies. Register area is deliberately not guessed.", "macro_requests": [
            {"role": "span_owner_sram_backing", "instances": banks, "bytes_per_instance": per_bank_span},
            {"role": "quota_accounted_pooled_queue_staging_shard", "instances": banks, "bytes_per_instance": pooled_queue_per_bank},
        ], "non_cacti_state": [{"role": "head_control_register_hot_state", "instances": banks, "entries_per_instance": ceil_div(counts["head_control"], banks), "entry_bits": ENTRY_BITS, "area_status": "not_estimated_without_library_or_synthesis", "reason": "A4.12.1 does not invent a register-cell area from an SRAM proxy."}], **common},
    ]


def mutate_cacti_config(template: str, size_bytes: int, node_um: float) -> str:
    replacements = {
        r"(?m)^-size \(bytes\) .*$": f"-size (bytes) {size_bytes}",
        r"(?m)^-block size \(bytes\) .*$": "-block size (bytes) 8",
        r"(?m)^-associativity .*$": "-associativity 1",
        r"(?m)^-read-write port .*$": "-read-write port 1",
        r"(?m)^-exclusive read port .*$": "-exclusive read port 0",
        r"(?m)^-exclusive write port .*$": "-exclusive write port 0",
        r"(?m)^-single ended read ports .*$": "-single ended read ports 0",
        r"(?m)^-UCA bank count .*$": "-UCA bank count 1",
        r"(?m)^-technology \(u\) .*$": f"-technology (u) {node_um:.3f}",
        r"(?m)^-output/input bus width .*$": "-output/input bus width 64",
        r'(?m)^-cache type "cache"$': '-cache type "ram"',
    }
    for pattern, replacement in replacements.items():
        template, count = re.subn(pattern, replacement, template)
        if count != 1:
            raise ValueError(f"CACTI template did not contain one mutable setting: {pattern}")
    return template


def parse_cacti_output(text: str) -> dict[str, float]:
    patterns = {
        "access_time_ns": r"Access time \(ns\):\s*([0-9.eE+-]+)",
        "cycle_time_ns": r"Cycle time \(ns\):\s*([0-9.eE+-]+)",
        "dynamic_read_energy_nj": r"Total dynamic read energy per access \(nJ\):\s*([0-9.eE+-]+)",
        "dynamic_write_energy_nj": r"Total dynamic write energy per access \(nJ\):\s*([0-9.eE+-]+)",
        "data_array_area_mm2": r"Data array: Area \(mm2\):\s*([0-9.eE+-]+)",
    }
    result = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text)
        if match is None:
            raise ValueError(f"CACTI output lacks {name}")
        result[name] = float(match.group(1))
    result["dynamic_read_energy_pj"] = result["dynamic_read_energy_nj"] * 1000.0
    result["dynamic_write_energy_pj"] = result["dynamic_write_energy_nj"] * 1000.0
    return result


def run_cacti(binary: Path, source_dir: Path, output_dir: Path, request: dict[str, Any], node_um: float) -> dict[str, Any]:
    # CACTI resolves its technology tables relative to its checkout.  Run with
    # that checkout as cwd while passing an absolute generated config path.
    # Otherwise the legacy binary can dereference missing technology state.
    output_dir = output_dir.resolve()
    configs = output_dir / "cacti_configs"
    raw = output_dir / "cacti_raw"
    configs.mkdir(exist_ok=True)
    raw.mkdir(exist_ok=True)
    template = (source_dir / "cache.cfg").read_text(encoding="utf-8")
    size = int(request["bytes_per_instance"])
    slug = f"{request['role']}_{size}B"
    config_path, raw_path = configs / f"{slug}.cfg", raw / f"{slug}.out"
    config_path.write_text(mutate_cacti_config(template, size, node_um), encoding="utf-8")
    completed = subprocess.run([str(binary.resolve()), "-infile", str(config_path.resolve())], cwd=source_dir.resolve(), check=True, text=True, capture_output=True)
    raw_path.write_text(completed.stdout, encoding="utf-8")
    parsed = parse_cacti_output(completed.stdout)
    return {**request, "config_path": str(config_path), "config_sha256": sha256_file(config_path), "raw_output_path": str(raw_path), "raw_output_sha256": sha256_file(raw_path), "per_instance_cacti_proxy": parsed, "aggregate_area_mm2": parsed["data_array_area_mm2"] * int(request["instances"]), "energy_boundary": "Per-access CACTI dynamic energy is retained only as a macro characterization input for A4.12.2. It is not aggregated into workload energy in A4.12.1."}


def trace_peak_summary(a4120: dict[str, Any]) -> dict[str, Any]:
    # A4.12.0 embeds A4.10 only as a hash-bound source; physical simultaneous
    # layer concurrency remains intentionally unknown here.
    return {"available_in_a4120": False, "reason": "A4.12.0 freezes the A4.10 logical contract and source hash, but does not reclassify context-wise queue observations into physical simultaneous-layer occupancy. A4.12.1 therefore does not use trace peaks to reduce provisioned capacity."}


def materialize_cacti_template(source_dir: Path, input_dir: Path, provenance: dict[str, Any]) -> Path:
    """Preserve the exact public CACTI template beside the result, never in /tmp."""
    destination = input_dir / "cacti_cache_template.cfg"
    shutil.copyfile(source_dir / "cache.cfg", destination)
    if sha256_file(destination) != provenance["template_sha256"]:
        raise AssertionError("CACTI template changed while materializing")
    provenance["materialized_template"] = str(destination)
    return destination


def main() -> None:
    args = parse_args()
    a4120 = require_a4120(args.a4120_report)
    provenance = cacti_provenance(args.cacti_binary, args.cacti_source_dir, args.technology_node_um)
    templates = candidate_templates(a4120)
    if args.preflight_only:
        print("A4.12.1 preflight passed: A4.12.0 binding, three candidate templates, and public CACTI provenance are valid; no output created and CACTI was not executed.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"A4.12.1 output directory already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    input_dir = args.output_dir / "input_artifacts"
    input_dir.mkdir()
    a4120_copy = input_dir / "a4120_source.json"
    shutil.copyfile(args.a4120_report, a4120_copy)
    if sha256_file(a4120_copy) != A4120_SHA256:
        raise AssertionError("A4.12.0 input changed while materializing")
    materialize_cacti_template(args.cacti_source_dir, input_dir, provenance)
    rows = []
    for candidate in templates:
        macros = [run_cacti(args.cacti_binary, args.cacti_source_dir, args.output_dir, request, args.technology_node_um) for request in candidate["macro_requests"]]
        rows.append({**candidate, "macro_rows": macros, "cacti_proxy_macro_area_mm2": sum(row["aggregate_area_mm2"] for row in macros), "register_area_included": not candidate["non_cacti_state"], "area_boundary": "This is a public-CACTI 0.032-um SRAM-proxy envelope for the listed macro instances only. It excludes controller, arbitration, scoreboard, commit, wiring, clocking, pads, physical layout, and any unestimated register state."})
    config = {"stage": "A4.12.1", "candidate_names": [row["name"] for row in templates], "technology_proxy_node_um": args.technology_node_um, "entry_bits": ENTRY_BITS, "layer_count_assumption": LAYER_COUNT, "cacti_proxy": "single-RW, single-bank, 8-byte block RAM configuration per listed macro instance"}
    report = {"schema_version": SCHEMA, "status": "complete", "created_at": datetime.now(timezone.utc).isoformat(), "git_commit": get_git_commit(), "execution_classification": "public-CACTI analytical macro proxy envelope over frozen logical contracts; not a PDK, measured macro, workload energy, cycle, throughput, architecture, or RTL result", "config": config, "config_hash": stable_hash(config), "input_artifacts": {"a4120_report_canonical_path": "analysis/experiments/route_a4120_metadata_interface_inventory_02/a4120_metadata_interface_inventory_report.json", "a4120_report_sha256": A4120_SHA256, "a4120_materialized_copy": str(a4120_copy), "cacti": provenance}, "logical_contract": a4120["interface_inventory"], "trace_peak_observation": trace_peak_summary(a4120), "candidate_rows": rows, "semantic_guards": {"a4120_exact_hash_and_immutability_guards_validated": True, "exactly_three_preregistered_macro_organizations_compared": True, "ha8_wide_service_requirement_not_relabelled_as_macro_ports": True, "logical_contract_and_physical_provisioning_separated": True, "payload_dependent_address_fields_remain_uninstantiated": True, "m3_register_area_not_invented": True, "no_cycle_throughput_or_workload_energy_claim": True, "no_queue_execution_scheduler_or_pruning_variant_introduced": True}, "boundaries": ["CACTI outputs characterize only listed SRAM proxy macros at its public 0.032-um technology model. They are not target-process or PDK numbers.", "M1/M2/M3 are representative physical-organization envelopes, not an exhaustive design-space search or selected implementation.", "The static 36-layer provisioning mapping is an explicit conservative organization assumption. It is neither an observed simultaneous-layer demand nor a proof that a smaller shared pool is safe.", "Single-operation latency and energy are retained as CACTI macro-characterization inputs only; A4.12.2 separately models latency, sustained issue rate, utilization, residence, commit throughput, and estimated dynamic energy."]}
    output = args.output_dir / "a4121_metadata_macro_envelope_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.12.1 complete: {output} sha256={sha256_file(output)} candidates={len(rows)}")


if __name__ == "__main__":
    main()
