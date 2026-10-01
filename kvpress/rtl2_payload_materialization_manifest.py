"""No-model validation for the RTL2.0a hot-payload interface closure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA = "kvzap-route-a-rtl2-0a-payload-materialization-1.0"
STATUS = "rtl2_0a_payload_interface_owner_closed_behavior_pending"
REQUIRED_TRANSACTIONS = frozenset(
    {"frontend_hot_payload_fragment", "hot_mature_payload_read_request", "hot_mature_payload_fragment"}
)
REQUIRED_OWNER_RESOURCES = frozenset(
    {
        "frontend_payload_materialization",
        "hot_payload_residency_and_maturity_egress",
        "retained_group_payload_request_context",
    }
)


class RTL2PayloadMaterializationError(ValueError):
    """Raised when the payload-interface contract hides a storage/owner choice."""


def load_manifest(path: str | Path) -> dict[str, Any]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RTL2PayloadMaterializationError("manifest root must be a JSON object")
    return loaded


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA or manifest.get("status") != STATUS:
        raise RTL2PayloadMaterializationError("unexpected RTL2.0a payload manifest identity")
    scope = manifest.get("scope")
    if not isinstance(scope, str) or "No payload storage implementation" not in scope:
        raise RTL2PayloadMaterializationError("scope must retain the no-storage boundary")
    for reference in _strings(manifest, "contract_references"):
        if not Path(reference).is_file():
            raise RTL2PayloadMaterializationError(f"missing contract reference: {reference}")

    anchor = _object(manifest, "anchor_payload_contract")
    expected = {
        "record_payload_bytes": 512,
        "fragment_bytes": 64,
        "fragments_per_record": 8,
        "fragment_data_width_bits": 512,
        "position_sidecar_bytes": 8,
        "payload_ref_width_bits": 64,
        "logical_page_records": 64,
    }
    if {key: anchor.get(key) for key in expected} != expected:
        raise RTL2PayloadMaterializationError("anchor payload sizes differ from the frozen Route-A contract")
    forbidden = set(_strings(anchor, "forbidden_interpretations"))
    if "payload_ref is a physical address" not in forbidden or "logical payload envelope selects an SRAM macro" not in forbidden:
        raise RTL2PayloadMaterializationError("payload interface must exclude address/macro interpretation")

    owners = _records(manifest, "owners")
    owner_resources = _unique(owners, "resource", "owner")
    if owner_resources != REQUIRED_OWNER_RESOURCES:
        raise RTL2PayloadMaterializationError("payload owner inventory differs")
    for owner in owners:
        for key in ("resource", "owner", "kind"):
            _required(owner, key)
        if not _strings(owner, "forbidden"):
            raise RTL2PayloadMaterializationError(f"owner lacks forbidden constraints: {owner['resource']}")
    hot = next(owner for owner in owners if owner["resource"] == "hot_payload_residency_and_maturity_egress")
    if hot["owner"] != "route_a_hot_source_path" or "pending_or_packed authority" not in hot["forbidden"]:
        raise RTL2PayloadMaterializationError("hot owner must remain sole payload/provenance owner without authority transfer")

    transactions = _records(manifest, "transactions")
    if _unique(transactions, "id", "transaction") != REQUIRED_TRANSACTIONS:
        raise RTL2PayloadMaterializationError("payload transaction inventory differs")
    by_id = {record["id"]: record for record in transactions}
    for transaction in transactions:
        for key in ("id", "producer", "consumer", "handshake", "ordering", "authority_effect", "completion_effect"):
            _required(transaction, key)
        if transaction["handshake"] != "decoupled_ready_valid":
            raise RTL2PayloadMaterializationError(f"transaction must use ready/valid: {transaction['id']}")
        if transaction["authority_effect"] != "none":
            raise RTL2PayloadMaterializationError(f"payload transport may not transfer authority: {transaction['id']}")
        fields = set(_strings(transaction, "fields"))
        if not set(_strings(transaction, "identity_fields")).issubset(fields):
            raise RTL2PayloadMaterializationError(f"identity field omitted from payload transaction: {transaction['id']}")
    ingress = by_id["frontend_hot_payload_fragment"]
    if ingress["producer"] != "frontend_payload_materializer" or ingress["consumer"] != "route_a_hot_source_path":
        raise RTL2PayloadMaterializationError("frontend materialization must terminate at the hot owner")
    if not {"fragment_index", "last", "data_512b", "payload_ref"}.issubset(set(ingress["fields"])):
        raise RTL2PayloadMaterializationError("frontend materialization lacks fragment/payload identity")
    request = by_id["hot_mature_payload_read_request"]
    response = by_id["hot_mature_payload_fragment"]
    if request["producer"] != "route_a_admission_publication_ingress_adapter" or request["consumer"] != "route_a_hot_source_path":
        raise RTL2PayloadMaterializationError("maturity egress request owner differs")
    if response["producer"] != "route_a_hot_source_path" or response["consumer"] != "route_a_admission_publication_ingress_adapter":
        raise RTL2PayloadMaterializationError("maturity egress response owner differs")
    if "transaction_group_tag" not in request["fields"] or "group_member_ordinal" not in response["fields"]:
        raise RTL2PayloadMaterializationError("maturity egress must retain immutable group association")

    assumptions = set(_strings(manifest, "environment_assumptions"))
    if not any("before it presents the matching immutable maturity disposition" in assumption for assumption in assumptions):
        raise RTL2PayloadMaterializationError("materialization-before-maturity environment assumption is required")
    guarantees = set(_strings(manifest, "dut_guarantees_for_later_behavior"))
    if not any("stale, duplicate, out-of-order" in guarantee for guarantee in guarantees):
        raise RTL2PayloadMaterializationError("later hot behavior must reject stale/duplicate/out-of-order fragments")
    follow_on = _object(manifest, "required_follow_on")
    if follow_on.get("behavioral_phase") != "rtl2_1a" or "simulation/reference backing only" not in str(follow_on.get("requires")):
        raise RTL2PayloadMaterializationError("follow-on must retain replaceable functional-storage boundary")
    labels = set(_strings(manifest, "evidence_labels"))
    if not {"no model/GPU", "no PPA claim", "no RTL correctness claim", "no new A4 DSE"}.issubset(labels):
        raise RTL2PayloadMaterializationError("payload evidence labels drifted")


def _object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RTL2PayloadMaterializationError(f"{key} must be an object")
    return value


def _records(parent: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = parent.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RTL2PayloadMaterializationError(f"{key} must be a list of objects")
    return value


def _strings(parent: dict[str, Any], key: str) -> list[str]:
    value = parent.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RTL2PayloadMaterializationError(f"{key} must be a nonempty string list")
    return value


def _unique(records: list[dict[str, Any]], key: str, label: str) -> frozenset[str]:
    values = [record.get(key) for record in records]
    if not all(isinstance(value, str) and value for value in values) or len(values) != len(set(values)):
        raise RTL2PayloadMaterializationError(f"duplicate or missing {label} identifier")
    return frozenset(values)


def _required(record: dict[str, Any], key: str) -> None:
    if not isinstance(record.get(key), str) or not record[key]:
        raise RTL2PayloadMaterializationError(f"record {record.get('id', record.get('resource'))!r} lacks {key}")
