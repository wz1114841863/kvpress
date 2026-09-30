"""No-model validation for the Gate-RTL0 interface-manifest planning artifact.

This module checks only hierarchy and unique-owner records before port records
are introduced.  It is not an RTL generator, an RTL implementation, a timing
model, or a hardware-performance model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "kvzap-route-a-rtl-entry-interface-manifest-1.0"
HIERARCHY_OWNER_STATUS = "hierarchy_owner_frozen_ports_pending"
PORTS_BOUND_STATUS = "ports_parameter_bound_markdown_consistent"
PORTS_BOUND_INTERFACE_STATUS = "complete_gate_rtl0_step_2"
REQUIRED_SIGNAL_FIELDS = frozenset(
    {
        "module",
        "port",
        "direction",
        "width",
        "clock",
        "reset",
        "handshake",
        "producer",
        "consumer",
        "parameter_source",
    }
)
REQUIRED_MODULES = frozenset(
    {
        "route_a_kv_subsystem_top",
        "route_a_lifecycle_adapter",
        "route_a_hot_source_path",
        "route_a_s2_gqa_source_wrapper",
        "route_a_direct_pending_endpoint_v1",
        "route_a_core_side_arbiter",
        "route_a_core_mem_if_v1",
        "route_a_m2_p3_wrapper",
        "route_a_page_manager",
        "route_a_merge_boundary",
        "route_a_component_status_collector",
    }
)
REQUIRED_OWNER_RESOURCES = frozenset(
    {
        "top_level_composition_only",
        "lifecycle_authority_and_terminal_association",
        "hot_source_residency",
        "s2_slot_generation_and_gqa_release",
        "direct_pending_transport_association",
        "r2_dependency_scoreboard_and_grant_cursor",
        "r1_core_memory_transaction_identity",
        "r3_m2_private_groups_and_p3_stage_state",
        "r4_observable_merge_state_and_numeric_fault",
        "r5_stream_descriptor_allocator_and_descriptor_visibility",
        "global_retirement_acceptance_and_drain_ack",
        "integration_named_status_serialization",
    }
)
REQUIRED_PORT_RECORD_IDS = frozenset(
    {
        "if_frontend_lifecycle_req",
        "if_runtime_retire_req",
        "if_lifecycle_terminal_rsp",
        "if_lifecycle_retire_ack",
        "if_lifecycle_component_status",
        "if_lifecycle_hot_control",
        "if_lifecycle_s2_control",
        "if_lifecycle_direct_pending_open",
        "if_source_partial_to_merge",
        "if_r4_partial_header",
        "if_r4_value_fragment",
        "if_r4_result_stub",
        "if_r4_numeric_fault",
        "if_merge_source_commit",
        "if_lifecycle_merge_req",
        "if_merge_lifecycle_rsp",
        "if_source_candidate_to_r2",
        "if_r2_core_mem_req",
        "if_r1_core_mem_rsp",
        "if_r1_external_memory",
        "if_r1_external_init_ack",
        "if_r2_source_delivery",
        "if_lifecycle_publish_req",
        "if_r3_r5_publish_visibility",
        "if_r5_r3_publish_ready",
        "if_r3_lifecycle_publish_ack",
    }
)
MATRIX_BEGIN = "<!-- BEGIN RTL_ENTRY_INTERFACE_MATRIX -->"
MATRIX_END = "<!-- END RTL_ENTRY_INTERFACE_MATRIX -->"


class RTLEntryManifestError(ValueError):
    """Raised when the non-RTL planning manifest violates its frozen schema."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load one JSON manifest without inferring defaults or implementation data."""
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RTLEntryManifestError("manifest root must be a JSON object")
    return loaded


def validate_manifest(manifest: dict[str, Any], *, require_interface_signals: bool = False) -> None:
    """Validate hierarchy/owner closure and, later, the signal-record shape."""
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise RTLEntryManifestError("unexpected manifest schema_version")
    status = manifest.get("status")
    if status not in {HIERARCHY_OWNER_STATUS, PORTS_BOUND_STATUS}:
        raise RTLEntryManifestError("unknown Gate-RTL0 manifest status")

    hierarchy = _object(manifest, "hierarchy")
    modules = _list(hierarchy, "modules")
    module_names = _unique_strings(modules, "name", "module")
    if module_names != REQUIRED_MODULES:
        missing = sorted(REQUIRED_MODULES - module_names)
        unexpected = sorted(module_names - REQUIRED_MODULES)
        raise RTLEntryManifestError(f"module inventory differs; missing={missing}, unexpected={unexpected}")
    if hierarchy.get("top_module") != "route_a_kv_subsystem_top":
        raise RTLEntryManifestError("top_module must be route_a_kv_subsystem_top")

    for module in modules:
        name = module["name"]
        if not isinstance(module.get("contract_references"), list) or not module["contract_references"]:
            raise RTLEntryManifestError(f"module {name} lacks contract_references")
        parent = module.get("parent")
        if name == hierarchy["top_module"]:
            if parent is not None:
                raise RTLEntryManifestError("top module must have null parent")
        elif parent != hierarchy["top_module"]:
            raise RTLEntryManifestError(f"module {name} must be a direct child of the frozen top module")

    endpoints = _list(manifest, "environment_endpoints")
    endpoint_names = _unique_strings(endpoints, "name", "environment endpoint")
    if module_names & endpoint_names:
        raise RTLEntryManifestError("environment endpoint may not also be a DUT module")

    owner_claims = _list(manifest, "owner_claims")
    resources = _unique_strings(owner_claims, "resource", "owner resource")
    if resources != REQUIRED_OWNER_RESOURCES:
        missing = sorted(REQUIRED_OWNER_RESOURCES - resources)
        unexpected = sorted(resources - REQUIRED_OWNER_RESOURCES)
        raise RTLEntryManifestError(f"owner-resource inventory differs; missing={missing}, unexpected={unexpected}")
    for claim in owner_claims:
        owner = claim.get("owner")
        if owner not in module_names:
            raise RTLEntryManifestError(f"owner claim {claim['resource']} names unknown module {owner!r}")
        for field in ("kind", "contract_reference", "transfer_boundary"):
            if not isinstance(claim.get(field), str) or not claim[field]:
                raise RTLEntryManifestError(f"owner claim {claim['resource']} lacks {field}")

    connections = _list(manifest, "connections")
    connection_names = _unique_strings(connections, "id", "connection")
    if not connection_names:
        raise RTLEntryManifestError("hierarchy/owner closure requires explicit connections")
    known_nodes = module_names | endpoint_names
    for connection in connections:
        for field in ("producer", "consumer"):
            if connection.get(field) not in known_nodes:
                raise RTLEntryManifestError(f"connection {connection['id']} has unknown {field}")
        if not isinstance(connection.get("contract_reference"), str) or not connection["contract_reference"]:
            raise RTLEntryManifestError(f"connection {connection['id']} lacks contract_reference")

    interface = _object(manifest, "interface_records")
    signal_fields = interface.get("required_signal_fields")
    if set(signal_fields or ()) != REQUIRED_SIGNAL_FIELDS:
        raise RTLEntryManifestError("required_signal_fields differs from the Gate-RTL0 contract")
    signals = _list(interface, "signals")
    if status == HIERARCHY_OWNER_STATUS:
        if signals:
            raise RTLEntryManifestError("Gate-RTL0.1 hierarchy status requires an empty signal list")
        if require_interface_signals:
            raise RTLEntryManifestError("full interface validation requires a ports-bound manifest")
        return
    if interface.get("status") != PORTS_BOUND_INTERFACE_STATUS:
        raise RTLEntryManifestError("ports-bound manifest has unexpected interface_records status")
    if not signals:
        raise RTLEntryManifestError("full interface validation requires at least one signal record")
    record_ids = _unique_strings(signals, "record_id", "port record")
    if record_ids != REQUIRED_PORT_RECORD_IDS:
        raise RTLEntryManifestError("ports-bound manifest does not contain the complete frozen port-record inventory")
    known_nodes = module_names | endpoint_names
    for signal in signals:
        missing = sorted(REQUIRED_SIGNAL_FIELDS - set(signal))
        if missing:
            raise RTLEntryManifestError(f"signal record lacks required fields: {missing}")
        for field in ("peer_port", "applicability", "contract_reference"):
            if not isinstance(signal.get(field), str) or not signal[field]:
                raise RTLEntryManifestError(f"signal record {signal['record_id']} lacks {field}")
        if signal["module"] not in module_names:
            raise RTLEntryManifestError(f"signal record {signal['record_id']} has non-DUT module")
        if signal["producer"] not in known_nodes or signal["consumer"] not in known_nodes:
            raise RTLEntryManifestError(f"signal record {signal['record_id']} has unknown endpoint")
        if signal["direction"] == "output" and signal["module"] != signal["producer"]:
            raise RTLEntryManifestError(f"output record {signal['record_id']} must name its producer module")
        if signal["direction"] == "input" and signal["module"] != signal["consumer"]:
            raise RTLEntryManifestError(f"input record {signal['record_id']} must name its consumer module")
        if signal["direction"] not in {"input", "output"}:
            raise RTLEntryManifestError(f"signal record {signal['record_id']} has unsupported direction")
        _validate_parameter_source(signal["parameter_source"])
        _validate_parameter_source(signal["contract_reference"])
        fields = signal.get("fields")
        if not isinstance(fields, list) or not fields:
            raise RTLEntryManifestError(f"signal record {signal['record_id']} lacks fields")
        for bundle_field in fields:
            if not isinstance(bundle_field, dict) or not all(isinstance(bundle_field.get(key), str) and bundle_field[key] for key in ("name", "width", "parameter_source")):
                raise RTLEntryManifestError(f"signal record {signal['record_id']} has malformed bundle field")
            _validate_parameter_source(bundle_field["parameter_source"])


def validate_markdown_matrix(manifest: dict[str, Any], matrix_path: str | Path) -> None:
    """Require the reviewed Markdown matrix to exactly match manifest records."""
    validate_manifest(manifest, require_interface_signals=True)
    text = Path(matrix_path).read_text(encoding="utf-8")
    if MATRIX_BEGIN not in text or MATRIX_END not in text:
        raise RTLEntryManifestError("Markdown matrix markers are missing")
    observed = text.split(MATRIX_BEGIN, 1)[1].split(MATRIX_END, 1)[0].strip()
    expected = render_markdown_matrix(manifest).strip()
    if observed != expected:
        raise RTLEntryManifestError("Markdown interface matrix differs from manifest")


def render_markdown_matrix(manifest: dict[str, Any]) -> str:
    """Render the canonical review table; this is documentation, not RTL generation."""
    rows = [
        "| Record ID | Module.port | Direction | Producer -> consumer | Width | Clock/reset | Handshake | Parameter source | Contract reference |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for signal in manifest["interface_records"]["signals"]:
        rows.append(
            "| {record_id} | {module}.{port} | {direction} | {producer} -> {consumer} | {width} | {clock} / {reset} | {handshake} | {parameter_source} | {contract_reference} |".format(**signal)
        )
    return "\n".join(rows)


def _validate_parameter_source(source: str) -> None:
    if not isinstance(source, str) or not source:
        raise RTLEntryManifestError("parameter source must be nonempty")
    path_text = source.split("#", 1)[0]
    if not Path(path_text).is_file():
        raise RTLEntryManifestError(f"parameter source does not exist: {path_text}")


def _object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RTLEntryManifestError(f"{key} must be a JSON object")
    return value


def _list(parent: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = parent.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTLEntryManifestError(f"{key} must be a list of JSON objects")
    return value


def _unique_strings(records: list[dict[str, Any]], field: str, label: str) -> set[str]:
    values = [record.get(field) for record in records]
    if not all(isinstance(value, str) and value for value in values):
        raise RTLEntryManifestError(f"every {label} requires a nonempty {field}")
    if len(set(values)) != len(values):
        raise RTLEntryManifestError(f"duplicate {label} {field}")
    return set(values)
