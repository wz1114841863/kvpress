#!/usr/bin/env python3
"""Check the refined Route-A split successor and count logical HDL state.

This is a generated-source gate, not a synthesis or PPA result.  Sequential
state is counted from declared ``reg`` objects that appear on a nonblocking
assignment left-hand side.  Literal unpacked dimensions are included, so an
emitted memory helper contributes its full logical bit capacity.  The report
keeps named array interiors, emitted memory helpers, and retained control
separate; it does not treat an array proxy as zero cost.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path


TOP = "route_a_control_projection"
SPLIT = "route_a_control_projection_split"

REQUIRED_TOP_PORT_TOKENS = (
    "external_core_mem_if_v1_request_valid",
    "functional_sidecar_work_out_valid",
    "functional_sidecar_payload_release_out_valid",
    "functional_sidecar_registry_allocate_in_valid",
    "functional_sidecar_read_issue_in_valid",
    "functional_r5_descriptor_service_request_valid",
    "functional_r5_descriptor_service_response_valid",
    "functional_partial_hot_offer_in_valid",
    "functional_partial_pending_offer_in_valid",
    "functional_partial_packed_offer_in_valid",
    "functional_r4_accepted_packet_out_valid",
    "functional_r4_merge_work_out_valid",
    "functional_r4_result_in_valid",
    "functional_r4_numeric_fault_in_valid",
    "attention_terminal_rsp_valid",
    "session_retire_ack_valid",
)

RETAINED_CONTROL_MODULES = (
    "route_a_admission_publication_ingress_adapter",
    "route_a_m2_production_control_owner",
    "route_a_metadata_admission_bridge",
    "route_a_m2_p3_wrapper",
    "route_a_page_manager",
    "route_a_s2_gqa_source_wrapper",
    "route_a_lifecycle_adapter",
    "route_a_core_side_arbiter",
    "route_a_core_mem_if_v1",
    "route_a_pending_descriptor_owner",
    "route_a_direct_pending_association_materializer",
    "route_a_packed_read_activation_binder",
)

ARRAY_INTERIOR_MODULES = (
    "route_a_m2_entry_array_boundary",
    "route_a_p3_stage_array_boundary",
    "route_a_r5_availability_array_boundary",
    "route_a_s2_payload_sidecar_array_boundary",
)

EXCLUDED_FUNCTIONAL_BACKING = (
    "descriptorEntryImage",
    "descriptorReadable",
    "descriptorValidRecords",
)

COMPACT_BRIDGE_REQUIRED = (
    "groupMemberMask",
    "groupMappingRef",
    "groupMappingOwner",
)

COMPACT_BRIDGE_FORBIDDEN = (
    "groupMembers_",
    "metadata_append_operand_out_bits_members_",
)

MODULE_LINE_RE = re.compile(r"^module\s+([A-Za-z_$][\w$]*)\b")
REG_RE = re.compile(
    r"^\s*reg\s+(?:signed\s+)?"
    r"(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?"
    r"([A-Za-z_$][\w$]*)"
    r"(?:\s*\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*;",
    re.MULTILINE,
)
NONBLOCKING_LHS_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\s*(?:\[[^;\n]*?\])?\s*<=")
POSEDGE_RE = re.compile(r"\balways(?:_ff)?\s*@?\s*\(\s*posedge\b")
MEMORY_HELPER_RE = re.compile(r".*_\d+x\d+$")


def fail(message: str) -> None:
    raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dimension(msb, lsb):
    if msb is None:
        return 1
    return abs(int(msb) - int(lsb)) + 1


def scan_module(path):
    declarations = {}
    assigned = set()
    module_names = []
    posedge_blocks = 0
    syn_black_box = False
    nonempty_body_lines = 0
    top_tokens = {token: False for token in REQUIRED_TOP_PORT_TOKENS}
    compact_required = {token: False for token in COMPACT_BRIDGE_REQUIRED}
    compact_forbidden = {token: False for token in COMPACT_BRIDGE_FORBIDDEN}
    excluded_backing = {token: False for token in EXCLUDED_FUNCTIONAL_BACKING}
    in_module = False
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            module_match = MODULE_LINE_RE.match(line)
            if module_match:
                module_names.append(module_match.group(1))
                in_module = True
            elif line.startswith("endmodule"):
                in_module = False
            elif in_module and line.strip() and not line.lstrip().startswith("//"):
                nonempty_body_lines += 1
            reg_match = REG_RE.match(line)
            if reg_match:
                packed_msb, packed_lsb, name, unpacked_msb, unpacked_lsb = reg_match.groups()
                packed = dimension(packed_msb or None, packed_lsb or None)
                unpacked = dimension(unpacked_msb or None, unpacked_lsb or None)
                declarations[name] = packed * unpacked
            assigned.update(NONBLOCKING_LHS_RE.findall(line))
            posedge_blocks += len(POSEDGE_RE.findall(line))
            syn_black_box = syn_black_box or "syn_black_box" in line
            for token in top_tokens:
                top_tokens[token] = top_tokens[token] or token in line
            for token in compact_required:
                compact_required[token] = compact_required[token] or token in line
            for token in compact_forbidden:
                compact_forbidden[token] = compact_forbidden[token] or token in line
            for token in excluded_backing:
                excluded_backing[token] = excluded_backing[token] or token in line
    if len(module_names) != 1:
        fail(f"expected exactly one module in {path}, found {module_names}")
    state = {name: declarations[name] for name in assigned if name in declarations}
    unresolved = sorted(name for name in assigned if name not in declarations)
    return {
        "module": module_names[0],
        "state_bits": sum(state.values()),
        "state_objects": len(state),
        "posedge_blocks": posedge_blocks,
        "unresolved_nonblocking_lhs": unresolved,
        "syn_black_box": syn_black_box,
        "nonempty_body_lines": nonempty_body_lines,
        "top_tokens": top_tokens,
        "compact_required": compact_required,
        "compact_forbidden": compact_forbidden,
        "excluded_backing": excluded_backing,
    }


def load_modules(split):
    files = sorted(path for path in split.glob("*.sv") if path.is_file())
    if not files:
        fail(f"no split SystemVerilog files under {split}")
    modules = {}
    for path in files:
        scanned = scan_module(path)
        name = scanned.pop("module")
        if name in modules:
            fail(f"duplicate module definition: {name}")
        scanned["path"] = str(path.relative_to(split.parent))
        modules[name] = scanned
    return modules, files


def classify_state(modules: dict) -> dict:
    details = {}
    for name, item in modules.items():
        details[name] = {
            "state_bits": item["state_bits"],
            "state_objects": item["state_objects"],
            "posedge_blocks": item["posedge_blocks"],
            "unresolved_nonblocking_lhs": item["unresolved_nonblocking_lhs"],
            "source": item["path"],
        }
    missing_arrays = [name for name in ARRAY_INTERIOR_MODULES if name not in details]
    if missing_arrays:
        fail(f"missing named array interiors: {missing_arrays}")
    array_names = set(ARRAY_INTERIOR_MODULES)
    helper_names = {name for name in details if MEMORY_HELPER_RE.fullmatch(name)}
    control_names = set(details) - array_names - helper_names

    def subtotal(names):
        return {
            "modules": sorted(names),
            "state_bits": sum(details[name]["state_bits"] for name in names),
            "state_objects": sum(details[name]["state_objects"] for name in names),
        }

    return {
        "all": subtotal(set(details)),
        "named_array_interiors": subtotal(array_names),
        "emitted_memory_helpers": subtotal(helper_names),
        "retained_control_and_other": subtotal(control_names),
        "per_module": dict(
            sorted(details.items(), key=lambda item: (-item[1]["state_bits"], item[0]))
        ),
    }


def inspect_root(root: Path, require_refinement: bool) -> dict:
    split = root / SPLIT
    if not split.is_dir():
        fail(f"missing split directory: {split}")
    modules, files = load_modules(split)
    if TOP not in modules:
        fail(f"missing top module {TOP}")
    missing_ports = [token for token, found in modules[TOP]["top_tokens"].items() if not found]
    if missing_ports:
        fail(f"missing typed top-level ports: {missing_ports}")
    missing_controls = [name for name in RETAINED_CONTROL_MODULES if name not in modules]
    if missing_controls:
        fail(f"missing retained control owners: {missing_controls}")
    for name in RETAINED_CONTROL_MODULES:
        if modules[name]["syn_black_box"] or modules[name]["nonempty_body_lines"] == 0:
            fail(f"retained control owner is empty or black-boxed: {name}")
    for name in ARRAY_INTERIOR_MODULES:
        if name not in modules:
            fail(f"missing typed array interior: {name}")
        if modules[name]["syn_black_box"] or modules[name]["nonempty_body_lines"] == 0:
            fail(f"raw functional successor array interior is empty or black-boxed: {name}")
    for token in EXCLUDED_FUNCTIONAL_BACKING:
        if any(item["excluded_backing"][token] for item in modules.values()):
            fail(f"functional R5 descriptor backing leaked into successor: {token}")
    compact = {
        "required_tokens": modules["route_a_metadata_admission_bridge"]["compact_required"],
        "forbidden_tokens": modules["route_a_metadata_admission_bridge"]["compact_forbidden"],
    }
    if require_refinement:
        missing = [token for token, found in compact["required_tokens"].items() if not found]
        leaked = [token for token, found in compact["forbidden_tokens"].items() if found]
        if missing or leaked:
            fail(f"compact metadata bridge mismatch: missing={missing}, leaked={leaked}")

    aggregate = hashlib.sha256()
    for path in files:
        relative = str(path.relative_to(root))
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(sha256_file(path).encode("ascii"))
        aggregate.update(b"\n")
    return {
        "root": str(root),
        "file_count": len(files),
        "sv_bytes": sum(path.stat().st_size for path in files),
        "closure_sha256": aggregate.hexdigest(),
        "top_ports": {token: True for token in REQUIRED_TOP_PORT_TOKENS},
        "retained_control_modules": list(RETAINED_CONTROL_MODULES),
        "typed_array_interiors": list(ARRAY_INTERIOR_MODULES),
        "compact_metadata_bridge": compact,
        "state": classify_state(modules),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--baseline-root", type=Path)
    args = parser.parse_args()

    current = inspect_root(args.root.resolve(), require_refinement=True)
    report = {
        "schema_version": "kvzap-route-a-control-refinement-successor-v1",
        "evidence_scope": "generated_logical_hdl_not_mapped_area_or_ppa",
        "current": current,
        "pass": True,
    }
    if args.baseline_root is not None:
        baseline = inspect_root(args.baseline_root.resolve(), require_refinement=False)
        current_bridge = current["state"]["per_module"]["route_a_metadata_admission_bridge"]["state_bits"]
        baseline_bridge = baseline["state"]["per_module"]["route_a_metadata_admission_bridge"]["state_bits"]
        report["baseline"] = baseline
        report["metadata_bridge_state_delta"] = {
            "baseline_bits": baseline_bridge,
            "current_bits": current_bridge,
            "delta_bits": current_bridge - baseline_bridge,
            "reduction_bits": baseline_bridge - current_bridge,
        }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bridge = current["state"]["per_module"]["route_a_metadata_admission_bridge"]
    print(
        "KVZAP_CONTROL_REFINEMENT_SUCCESSOR_CHECK_PASS "
        f"files={current['file_count']} bridge_state_bits={bridge['state_bits']} report={args.report}"
    )


if __name__ == "__main__":
    main()
