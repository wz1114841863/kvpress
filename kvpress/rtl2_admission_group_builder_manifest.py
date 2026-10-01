"""No-model validation for the RTL2.0b retained-group builder contract."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

SCHEMA = "kvzap-route-a-rtl2-0b-admission-group-builder-1.0"
STATUS = "rtl2_0b_group_builder_interface_owner_closed_behavior_pending"
REQUIRED_CARRIERS = frozenset({"r6_retained_member_in", "adapter_to_r5_allocate", "r5_allocation_to_adapter", "adapter_to_r3_p3_claim", "r3_claim_ack_to_adapter", "adapter_to_r3_member_join"})

class RTL2AdmissionGroupBuilderError(ValueError):
    pass

def load_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise RTL2AdmissionGroupBuilderError("manifest root must be an object")
    return value

def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA or manifest.get("status") != STATUS: raise RTL2AdmissionGroupBuilderError("unexpected RTL2.0b manifest identity")
    if "No P3 payload movement" not in str(manifest.get("scope")): raise RTL2AdmissionGroupBuilderError("scope must retain no-dataflow boundary")
    for path in _strings(manifest, "contract_references"):
        if not Path(path).is_file(): raise RTL2AdmissionGroupBuilderError(f"missing contract reference: {path}")
    anchor = _object(manifest, "anchor")
    if (anchor.get("max_group_members"), anchor.get("active_kv_head_groups"), anchor.get("pack_engines"), anchor.get("p3_reservation_owner_value")) != (64, 1, 1, 0): raise RTL2AdmissionGroupBuilderError("anchor group/packer/reservation values drifted")
    if "not an R1 request ID" not in str(anchor.get("p3_reservation_owner_meaning")): raise RTL2AdmissionGroupBuilderError("P3 owner must remain local reservation-only")
    if "contiguous first-entry-plus-count reconstruction" not in _strings(anchor, "forbidden"): raise RTL2AdmissionGroupBuilderError("group builder must forbid span reconstruction")
    child = _object(manifest, "child")
    if child.get("name") != "route_a_admission_publication_ingress_adapter" or child.get("parent") != "route_a_kv_subsystem_top": raise RTL2AdmissionGroupBuilderError("group builder hierarchy differs")
    if "hot/pending/packed authority" not in _strings(child, "does_not_own"): raise RTL2AdmissionGroupBuilderError("group builder must not own authority")
    carriers = _records(manifest, "carriers")
    if _ids(carriers) != REQUIRED_CARRIERS: raise RTL2AdmissionGroupBuilderError("group builder carrier inventory differs")
    by_id = {row["id"]: row for row in carriers}
    for row in carriers:
        for key in ("id", "producer", "consumer", "rule", "authority_effect"): _required(row, key)
        if not _strings(row, "fields") or not _strings(row, "identity_fields"): raise RTL2AdmissionGroupBuilderError(f"carrier lacks fields: {row['id']}")
    if by_id["adapter_to_r5_allocate"]["producer"] != child["name"] or by_id["adapter_to_r5_allocate"]["consumer"] != "route_a_page_manager": raise RTL2AdmissionGroupBuilderError("R5 allocation ownership differs")
    if by_id["adapter_to_r3_p3_claim"]["producer"] != child["name"] or "owner is the anchor-local reservation value 0" not in by_id["adapter_to_r3_p3_claim"]["rule"]: raise RTL2AdmissionGroupBuilderError("P3 claim owner provenance differs")
    if by_id["adapter_to_r3_member_join"]["authority_effect"] != "the original R6 hot_to_pending transition is relayed without duplication or change": raise RTL2AdmissionGroupBuilderError("R6 authority relay must be exact")
    order = set(_strings(manifest, "state_and_order"))
    if not any("non-contiguous entry_id values" in item for item in order) or not any("R5 allocation precedes P3 claim" in item for item in order): raise RTL2AdmissionGroupBuilderError("group ordering loses non-contiguous or allocation-before-claim rule")
    if not any("no P3 claim" in item for item in _strings(manifest, "fault_and_reset")): raise RTL2AdmissionGroupBuilderError("partial group must remain non-visible")
    follow = _object(manifest, "required_follow_on")
    if follow.get("behavioral_phase") != "rtl2_1a" or "logical 64-member bound" not in str(follow.get("requires")): raise RTL2AdmissionGroupBuilderError("follow-on scope differs")

def _object(x: dict[str, Any], key: str) -> dict[str, Any]:
    value=x.get(key)
    if not isinstance(value, dict): raise RTL2AdmissionGroupBuilderError(f"{key} must be object")
    return value
def _records(x: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value=x.get(key)
    if not isinstance(value, list) or not all(isinstance(v,dict) for v in value): raise RTL2AdmissionGroupBuilderError(f"{key} must be object list")
    return value
def _strings(x: dict[str, Any], key: str) -> list[str]:
    value=x.get(key)
    if not isinstance(value,list) or not value or not all(isinstance(v,str) and v for v in value): raise RTL2AdmissionGroupBuilderError(f"{key} must be string list")
    return value
def _ids(rows: list[dict[str, Any]]) -> frozenset[str]:
    ids=[row.get("id") for row in rows]
    if not all(isinstance(i,str) and i for i in ids) or len(ids)!=len(set(ids)): raise RTL2AdmissionGroupBuilderError("carrier IDs missing or duplicate")
    return frozenset(ids)
def _required(row: dict[str, Any], key: str) -> None:
    if not isinstance(row.get(key),str) or not row[key]: raise RTL2AdmissionGroupBuilderError(f"carrier {row.get('id')!r} lacks {key}")
