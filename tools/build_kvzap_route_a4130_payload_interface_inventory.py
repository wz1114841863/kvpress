#!/usr/bin/env python3
"""Freeze the A4.13.0 Route-A payload software interface; no physical PPA."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash


SCHEMA = "kvzap-route-a4130-payload-interface-inventory-1.0"
EXPECTED_A4112B = (
    "kvzap-route-a4112b-external-storage-binding-1.0",
    "57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3",
)
EXPECTED_A4120 = (
    "kvzap-route-a4120-metadata-interface-inventory-1.0",
    "e5a7ad30b45be7acbda7c2b0b788fdfa4ee74553d6fc93bc9317dce0c4be3534",
)
REQUIRED_WORKLOADS = {"retrieval", "summarization", "reasoning"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "A4.13.0 Route-A payload interface inventory. It freezes software-visible "
            "K/V word/page/lifecycle facts only; it does not estimate traffic, PPA, "
            "cycles, throughput, or choose a physical payload architecture."
        )
    )
    parser.add_argument("--a4112b-report", type=Path, required=True, help="Exact accepted A4.11.2b report.")
    parser.add_argument("--a4120-report", type=Path, required=True, help="Exact accepted A4.12.0 report.")
    parser.add_argument(
        "--edge-target",
        type=Path,
        default=Path("analysis/qwen3_8b_edge_target_v0.json"),
        help="Tracked Qwen3-8B dimensional descriptor (default: %(default)s).",
    )
    parser.add_argument(
        "--admission-shadow-source",
        type=Path,
        default=Path("kvpress/admission_shadow.py"),
        help="Software reference containing separate packed K/V page allocation.",
    )
    parser.add_argument(
        "--route-a-attention-source",
        type=Path,
        default=Path("kvpress/route_a_attention.py"),
        help="Software reference containing Route-A logical source and merge semantics.",
    )
    parser.add_argument("--preflight-only", action="store_true", help="Validate authorities and dimensional contract without creating output.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return parser.parse_args()


def read_exact_report(path: Path, expected: tuple[str, str], label: str) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != expected[1]:
        raise ValueError(f"A4.13.0 requires exact accepted {label} SHA-256")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != expected[0] or report.get("status") != "complete":
        raise ValueError(f"{label} is incomplete or schema-incompatible")
    return report


def payload_layout(*, head_dim: int, scalar_bits: int, page_tokens: int, position_bits: int) -> dict[str, int]:
    if min(head_dim, scalar_bits, page_tokens, position_bits) <= 0 or scalar_bits % 8 or position_bits % 8:
        raise ValueError("payload dimensions must be positive whole-byte quantities")
    key_bytes = head_dim * scalar_bits // 8
    value_bytes = key_bytes
    token_bytes = key_bytes + value_bytes
    page_payload_bytes = page_tokens * token_bytes
    position_sidecar_bytes = page_tokens * position_bits // 8
    return {
        "key_word_bits": key_bytes * 8,
        "key_word_bytes": key_bytes,
        "value_word_bits": value_bytes * 8,
        "value_word_bytes": value_bytes,
        "kv_token_word_bits": token_bytes * 8,
        "kv_token_word_bytes": token_bytes,
        "page_payload_bits": page_payload_bytes * 8,
        "page_payload_bytes": page_payload_bytes,
        "logical_position_sidecar_bits": position_sidecar_bytes * 8,
        "logical_position_sidecar_bytes": position_sidecar_bytes,
        "reference_page_payload_plus_position_sidecar_bytes": page_payload_bytes + position_sidecar_bytes,
    }


def validate_a4112b(report: dict[str, Any]) -> None:
    guards = report.get("semantic_guards", {})
    needed = (
        "a4111_external_storage_exact_token_guard_remains_bound",
        "trace_on_external_storage_is_token_identical_to_trace_off_and_dense",
        "prefill_armed_external_storage_lifecycle_observed",
        "fixed_a410_parameters_not_retuned",
        "unmapped_hardware_fields_not_synthesized",
    )
    if not all(guards.get(key) is True for key in needed):
        raise ValueError("A4.11.2b external-storage lifecycle/token guards are incomplete")
    workloads = report.get("workloads", [])
    if {row.get("workload") for row in workloads} != REQUIRED_WORKLOADS:
        raise ValueError("A4.11.2b workload coverage changed")
    for row in workloads:
        direct = row.get("direct_software_observation", {})
        if int(direct.get("logical_admission_service_tokens", -1)) != int(direct.get("matured_kept_tokens", -2)):
            raise ValueError("A4.11.2b retained/matured lifecycle accounting is inconsistent")
        if int(direct.get("trace_end_residual_pending_tokens", -1)) != 0:
            raise ValueError("A4.13.0 requires accepted A4.11.2b zero trace-end pending residual")
        conversion = row.get("fixed_token_span_transaction_conversion", {})
        if int(conversion.get("token_to_span_tokens", -1)) != 64:
            raise ValueError("A4.11.2b token-to-span contract changed from 64")


def validate_target(target: dict[str, Any]) -> dict[str, int]:
    model = target.get("model", {})
    route_a = target.get("route_a", {})
    expected = {
        "hf_id": "Qwen/Qwen3-8B",
        "num_hidden_layers": 36,
        "num_key_value_heads": 8,
        "head_dim": 128,
        "cache_dtype": "bfloat16",
        "kv_bytes_per_layer_head_token": 512,
    }
    if any(model.get(key) != value for key, value in expected.items()):
        raise ValueError("tracked Qwen3-8B payload dimensional descriptor changed")
    if int(route_a.get("hot_window_tokens", -1)) != 128 or 64 not in route_a.get("page_tokens_candidates", []):
        raise ValueError("tracked Route-A window/page contract is incompatible with A4.13.0")
    return {"layers": 36, "kv_heads": 8, "head_dim": 128, "scalar_bits": 16, "page_tokens": 64, "window_tokens": 128, "admission_budget_tokens": 512}


def validate_source(path: Path, required_fragments: tuple[str, ...], label: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    text = path.read_text(encoding="utf-8")
    if not all(fragment in text for fragment in required_fragments):
        raise ValueError(f"{label} no longer contains required A4.13.0 software-reference interface fragments")
    return sha256_file(path)


def validate(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, int], dict[str, str]]:
    a4112b = read_exact_report(args.a4112b_report, EXPECTED_A4112B, "A4.11.2b")
    a4120 = read_exact_report(args.a4120_report, EXPECTED_A4120, "A4.12.0")
    validate_a4112b(a4112b)
    target = json.loads(args.edge_target.read_text(encoding="utf-8")) if args.edge_target.is_file() else None
    if target is None:
        raise FileNotFoundError(f"missing edge target descriptor: {args.edge_target}")
    dimensions = validate_target(target)
    layout = payload_layout(head_dim=dimensions["head_dim"], scalar_bits=dimensions["scalar_bits"], page_tokens=dimensions["page_tokens"], position_bits=64)
    if layout["kv_token_word_bytes"] != 512:
        raise ValueError("derived K+V token payload disagrees with frozen model descriptor")
    source_hashes = {
        "admission_shadow": validate_source(args.admission_shadow_source, ("self.keys.append", "self.values.append", "position_metadata_bytes"), "admission-shadow source"),
        "route_a_attention": validate_source(args.route_a_attention_source, ("online_softmax_merge", "packed", "pending"), "Route-A attention source"),
    }
    return a4112b, target, layout, source_hashes


def materialize(output_dir: Path, paths: dict[str, Path]) -> dict[str, dict[str, str]]:
    destination = output_dir / "input_artifacts"
    destination.mkdir()
    result: dict[str, dict[str, str]] = {}
    for label, source in paths.items():
        target = destination / source.name
        shutil.copyfile(source, target)
        result[label] = {"source_path": str(source), "materialized_copy": str(target), "sha256": sha256_file(target)}
    return result


def workload_rows(a4112b: dict[str, Any], layout: dict[str, int]) -> list[dict[str, Any]]:
    rows = []
    for row in sorted(a4112b["workloads"], key=lambda item: str(item["workload"])):
        direct = row["direct_software_observation"]
        retained = int(direct["matured_kept_tokens"])
        rows.append({
            "workload": row["workload"],
            "direct_software_observation": {
                "matured_kept_tokens": retained,
                "packed_page_count_per_head": direct["packed_page_count_per_head"],
                "packed_full_page_count_per_head": direct["packed_full_page_count_per_head"],
                "per_head_pending_after_maturity": direct["per_head_pending_after_maturity"],
                "per_head_pending_after_service": direct["per_head_pending_after_service"],
                "trace_end_residual_pending_tokens": direct["trace_end_residual_pending_tokens"],
            },
            "deterministic_reference_layout_interpretation": {
                "matured_kept_kv_payload_bytes": retained * layout["kv_token_word_bytes"],
                "matured_kept_logical_position_sidecar_bytes": retained * layout["logical_position_sidecar_bytes"] // 64,
                "boundary": "This multiplies accepted software lifecycle token counts by the fixed reference word/sidecar layout. It is not allocated physical capacity, memory traffic, transfer volume, bandwidth, or realized storage saving.",
            },
        })
    return rows


def main() -> None:
    args = parse_args()
    a4112b, target, layout, source_hashes = validate(args)
    if args.preflight_only:
        print("A4.13.0 preflight passed: exact A4.11.2b/A4.12.0 authorities, Qwen payload dimensions, lifecycle guards, and reference-source interface validated; no output created.")
        return
    if args.output_dir.exists():
        raise FileExistsError(f"output directory already exists: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    artifacts = materialize(args.output_dir, {
        "a4112b_report": args.a4112b_report,
        "a4120_report": args.a4120_report,
        "qwen3_8b_edge_target": args.edge_target,
        "admission_shadow_source": args.admission_shadow_source,
        "route_a_attention_source": args.route_a_attention_source,
    })
    dimensions = {"model": "Qwen/Qwen3-8B", "layers": 36, "kv_heads": 8, "head_dim": 128, "cache_scalar_bits": 16, "cache_scalar_reference_encoding": "bfloat16 software cache", "window_tokens": 128, "packed_page_tokens": 64, "admission_budget_tokens": 512}
    config = {"stage": "A4.13.0", "payload_scope": "external-storage software payload interface inventory", "dimensions": dimensions, "a4112b_sha256": EXPECTED_A4112B[1], "a4120_sha256": EXPECTED_A4120[1]}
    report = {
        "schema_version": SCHEMA,
        "status": "complete",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "execution_classification": "software-interface and deterministic-dimensional inventory; not a physical payload architecture, PPA, traffic, cycle, throughput, or RTL result",
        "config": config,
        "config_hash": stable_hash(config),
        "input_artifacts": artifacts,
        "authority_bindings": {
            "a4112b_external_storage_lifecycle": {"schema_version": EXPECTED_A4112B[0], "sha256": EXPECTED_A4112B[1], "role": "accepted exact-token external-storage lifecycle and scalar packed/pending observations"},
            "a4120_metadata_interface_inventory": {"schema_version": EXPECTED_A4120[0], "sha256": EXPECTED_A4120[1], "role": "separate fixed metadata/control logical service contract; not payload physical provisioning"},
            "software_reference_source_hashes": source_hashes,
        },
        "fixed_reference_dimensions": dimensions,
        "deterministic_payload_layout": {
            **layout,
            "layout_scope": "separate K and V software-reference arrays per (layer, KV head), with an eight-byte logical-position sidecar per retained token",
            "not_a_physical_selection": True,
        },
        "payload_lifecycle_interface": {
            "states": ["hot_window", "logical_pending_after_maturity", "packed_cold_append", "packed_page_seal", "multi_source_attention", "online_softmax_merge"],
            "hot_window_tokens": 128,
            "packed_page_tokens": 64,
            "admission_budget_tokens": 512,
            "storage_scope": "independent append-only packed cold pages per (layer, KV head) in the accepted software reference",
            "attention_source_semantics": "hot + pending + packed-cold logical sources; their partial results must preserve the existing online-softmax merge semantics",
            "hardware_event_boundary": "No lifecycle state is asserted to be a physical transfer, port access, ready event, commit cycle, bank operation, or attention schedule.",
        },
        "workload_rows": workload_rows(a4112b, layout),
        "physical_parameters_intentionally_unresolved": [
            "physical page count and page-ID/handle/address widths", "payload bank mapping and page-table encoding", "pending-KV capacity/location/ownership and movement or DMA", "SRAM versus HBM/DRAM tiering, burst layout, ports, and bandwidth", "physical provisioning scope across layers and heads", "query/K/V datapath, partial-softmax state placement, arithmetic precision, and merge implementation", "cycle, sustained issue rate, area, energy, traffic, and realized serving benefit",
        ],
        "semantic_guards": {
            "exact_a4112b_external_storage_token_and_lifecycle_guards_remain_bound": True,
            "a4120_logical_queue_contract_not_retuned_or_physicalized": True,
            "original_mask_pruning_admission_and_commit_semantics_not_changed": True,
            "reference_separate_k_v_page_layout_verified": True,
            "logical_position_sidecar_not_misrepresented_as_physical_address_or_pte": True,
            "no_payload_tier_bank_port_dma_or_attention_engine_selected": True,
            "no_physical_traffic_area_energy_cycle_throughput_or_net_benefit_claim": True,
            "no_new_queue_execution_scheduler_or_granularity_variant": True,
        },
        "boundaries": [
            "The page-byte arithmetic is a deterministic interpretation of the accepted Qwen software-cache tensor shape and scalar width, not a memory macro or allocator provisioning result.",
            "A4.11.2b packed/pending counters are direct software observations. Their byte products are neither physical occupancy nor data movement without a later allocation and transfer contract.",
            "A4.12 metadata logical capacities remain a separate contract. This inventory does not multiply them by 36 layers, select a payload SRAM, or infer a physical address width.",
            "A4.13 must next bound physical storage/movement and packed-attention organization before A4.14 can make a full Route-A net-benefit ledger.",
        ],
    }
    output = args.output_dir / "a4130_payload_interface_inventory_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A4.13.0 complete: {output} sha256={hashlib.sha256(output.read_bytes()).hexdigest()} workloads={len(report['workload_rows'])}")


if __name__ == "__main__":
    main()
