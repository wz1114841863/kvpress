"""No-model validation for RTL2.2.0 delivery-context reconciliation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "kvzap-route-a-rtl2-2-0-delivery-context-reconciliation-1.0"
STATUS = "rtl2_2_0_provenance_interface_reconciliation_complete"
READ_TARGETS = frozenset({"p3_pending_read", "s2_full_fill", "s2_packed_fill", "direct_pending_read"})
WRITE_TARGETS = frozenset({"packed_write_terminal", "descriptor_maintenance_terminal"})
IDENTITY_FIELDS = frozenset({"delivery_context_ref", "transaction_identity", "reset_epoch", "candidate_class", "target_kind", "target_identity_generation"})


class RTL22DeliveryContextReconciliationError(ValueError):
    pass


def load_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RTL22DeliveryContextReconciliationError("manifest root must be object")
    return value


def validate_manifest(manifest: dict[str, Any], root: str | Path) -> None:
    root_path = Path(root)
    if manifest.get("schema_version") != SCHEMA or manifest.get("status") != STATUS:
        raise RTL22DeliveryContextReconciliationError("unexpected RTL2.2.0 manifest identity")
    if "does not activate Chisel behavior" not in str(manifest.get("scope")):
        raise RTL22DeliveryContextReconciliationError("scope loses no-behavior boundary")

    artifacts = _records(manifest, "input_artifacts")
    expected_paths = {
        "analysis/rtl2_0c_r2_ingress_delivery_context_manifest.json",
        "analysis/rtl2_0d_typed_delivery_router_manifest.json",
        "analysis/rtl2_scoreboard_event_schema.json",
    }
    if _ids(artifacts, "path") != expected_paths:
        raise RTL22DeliveryContextReconciliationError("input artifact inventory differs")
    for artifact in artifacts:
        path = root_path / artifact["path"]
        if not path.is_file():
            raise RTL22DeliveryContextReconciliationError(f"missing input artifact: {artifact['path']}")
        expected_hash = artifact.get("sha256")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if not isinstance(expected_hash, str) or actual_hash != expected_hash:
            raise RTL22DeliveryContextReconciliationError(f"input artifact hash differs: {artifact['path']}")

    correction = _object(manifest, "historical_annotation_correction")
    if correction.get("historical_artifact") != "analysis/rtl2_0c_r2_ingress_delivery_context_manifest.json":
        raise RTL22DeliveryContextReconciliationError("historical annotation source differs")
    if correction.get("logical_class") != "pack_read" or correction.get("historical_activation") != "future_rtl2_1b" or correction.get("reconciled_activation") != "rtl2_2":
        raise RTL22DeliveryContextReconciliationError("pack_read activation correction differs")
    if correction.get("historical_artifact_mutation") is not False:
        raise RTL22DeliveryContextReconciliationError("historical artifact must remain immutable")

    owners = _object(manifest, "owner_freeze")
    if owners.get("r2_owner") != "route_a_core_side_arbiter" or owners.get("registry_owner") != "route_a_delivery_context_registry" or owners.get("router_owner") != "route_a_typed_delivery_router":
        raise RTL22DeliveryContextReconciliationError("owner freeze differs")
    if "must not allocate contexts" not in str(owners.get("top_rule")):
        raise RTL22DeliveryContextReconciliationError("top composition prohibition missing")

    typed_read = _object(manifest, "typed_read_fragment")
    if set(_strings(typed_read, "identity_fields")) != IDENTITY_FIELDS:
        raise RTL22DeliveryContextReconciliationError("typed read identity fields differ")
    if not {"fragment_index", "last", "status", "data_512b"}.issubset(_strings(typed_read, "fragment_fields")):
        raise RTL22DeliveryContextReconciliationError("typed read fragment fields incomplete")
    if set(_strings(typed_read, "required_target_kinds")) != READ_TARGETS:
        raise RTL22DeliveryContextReconciliationError("typed read target inventory differs")
    if "no endpoint mutation" not in str(typed_read.get("rule")):
        raise RTL22DeliveryContextReconciliationError("typed read stale exclusion missing")

    typed_write = _object(manifest, "typed_write_terminal")
    if set(_strings(typed_write, "required_target_kinds")) != WRITE_TARGETS:
        raise RTL22DeliveryContextReconciliationError("typed write target inventory differs")
    if "distinct from read fragments" not in str(typed_write.get("rule")):
        raise RTL22DeliveryContextReconciliationError("read/write separation missing")

    activation = _records(manifest, "producer_activation_boundary")
    by_class = {record.get("logical_class"): record for record in activation}
    if set(by_class) != {"pack_read", "s2_packed", "direct_pending", "s2_full"}:
        raise RTL22DeliveryContextReconciliationError("producer activation inventory differs")
    if by_class["pack_read"].get("activation") != "rtl2_2_transport_only":
        raise RTL22DeliveryContextReconciliationError("pack_read scope differs")
    if by_class["s2_packed"].get("activation") != "deferred_rtl2_3_functional_storage_endpoint" or by_class["direct_pending"].get("activation") != "deferred_rtl2_3_functional_storage_endpoint":
        raise RTL22DeliveryContextReconciliationError("S2/direct deferral differs")

    scoreboard = _object(manifest, "scoreboard_binding")
    if scoreboard.get("event") != "fragment_deliver" or scoreboard.get("activation_phase") != "rtl2_2" or scoreboard.get("current_state") != "schema_declared_adapter_behavior_deferred":
        raise RTL22DeliveryContextReconciliationError("scoreboard binding differs")
    deferred = set(_strings(manifest, "must_remain_deferred"))
    if not any("functional payload storage" in item for item in deferred) or not any("physical SRAM macro" in item for item in deferred):
        raise RTL22DeliveryContextReconciliationError("storage or realization deferral missing")


def _object(source: dict[str, Any], key: str) -> dict[str, Any]:
    value = source.get(key)
    if not isinstance(value, dict):
        raise RTL22DeliveryContextReconciliationError(f"{key} must be object")
    return value


def _records(source: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = source.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTL22DeliveryContextReconciliationError(f"{key} must be object list")
    return value


def _strings(source: dict[str, Any], key: str) -> list[str]:
    value = source.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RTL22DeliveryContextReconciliationError(f"{key} must be nonempty string list")
    return value


def _ids(rows: list[dict[str, Any]], key: str) -> set[str]:
    values = [row.get(key) for row in rows]
    if not all(isinstance(value, str) and value for value in values) or len(values) != len(set(values)):
        raise RTL22DeliveryContextReconciliationError(f"{key} missing or duplicate")
    return set(values)
