"""No-model validation for RTL2.0c R2 ingress/context ownership."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
SCHEMA="kvzap-route-a-rtl2-0c-r2-ingress-delivery-context-1.0"
STATUS="rtl2_0c_r2_ingress_and_delivery_context_owner_closed_behavior_pending"
CLASSES=frozenset({"s2_full","s2_packed","direct_pending","pack_read","pack_write","descriptor_maintenance"})
CARRIERS=frozenset({"producer_to_context_allocate","context_bound_candidate_to_r2","r2_to_r1_request","r2_to_delivery_resolution","router_to_context_resolve","context_to_exact_target"})
class RTL2R2IngressDeliveryContextError(ValueError): pass
def load_manifest(path:str|Path)->dict[str,Any]:
    value=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise RTL2R2IngressDeliveryContextError("manifest root must be object")
    return value
def validate_manifest(m:dict[str,Any])->None:
    if m.get("schema_version")!=SCHEMA or m.get("status")!=STATUS: raise RTL2R2IngressDeliveryContextError("unexpected RTL2.0c manifest identity")
    if "No behavioral R2 rewrite" not in str(m.get("scope")): raise RTL2R2IngressDeliveryContextError("scope must retain no-behavior boundary")
    for p in _strings(m,"contract_references"):
        if not Path(p).is_file(): raise RTL2R2IngressDeliveryContextError(f"missing contract reference: {p}")
    r2=_object(m,"r2_owner_boundary")
    if r2.get("owner")!="route_a_core_side_arbiter": raise RTL2R2IngressDeliveryContextError("R2 owner differs")
    if "delivery-context decode" not in _strings(r2,"does_not_own") or "one logical R1 request/output path" not in _strings(r2,"retains"): raise RTL2R2IngressDeliveryContextError("R2 boundary loses opaque-context or sole-R1 rule")
    classes=_records(m,"candidate_classes")
    if _ids(classes,"class")!=CLASSES: raise RTL2R2IngressDeliveryContextError("candidate class inventory differs")
    reads={x["class"] for x in classes if x.get("read_rotation_member")}
    if reads!={"s2_full","s2_packed","direct_pending","pack_read"}: raise RTL2R2IngressDeliveryContextError("read-class membership differs")
    desc=next(x for x in classes if x["class"]=="descriptor_maintenance")
    if desc.get("producer_owner")!="route_a_page_manager": raise RTL2R2IngressDeliveryContextError("R5 must remain descriptor producer")
    ingress=_object(m,"logical_ingress")
    if ingress.get("name")!="R2CandidateIngressByClass" or "R2 transports but never decodes it" not in str(ingress.get("context_rule")): raise RTL2R2IngressDeliveryContextError("logical ingress loses opaque context rule")
    if "no top/adapter selection is permitted" not in str(ingress.get("same_opportunity_rule")): raise RTL2R2IngressDeliveryContextError("ingress permits external selection")
    registry=_object(m,"delivery_context_registry")
    if registry.get("name")!="route_a_delivery_context_registry" or registry.get("parent")!="route_a_kv_subsystem_top": raise RTL2R2IngressDeliveryContextError("delivery-context registry hierarchy differs")
    if "R2 eligibility/FIFO/credit/cursor" not in _strings(registry,"does_not_own"): raise RTL2R2IngressDeliveryContextError("registry must not own R2 arbitration")
    if not {"delivery_context_ref","transaction_identity","reset_epoch","target_identity_generation"}.issubset(_strings(registry,"context_fields")): raise RTL2R2IngressDeliveryContextError("registry identity fields incomplete")
    forbidden=set(_strings(registry,"forbidden"))
    if not {"R2 context decode","ref reuse while live","stale response match after reuse","second R1 path"}.issubset(forbidden): raise RTL2R2IngressDeliveryContextError("registry safety prohibitions incomplete")
    carriers=_records(m,"carriers")
    if _ids(carriers,"id")!=CARRIERS: raise RTL2R2IngressDeliveryContextError("carrier inventory differs")
    by={x["id"]:x for x in carriers}
    if by["r2_to_delivery_resolution"].get("producer")!="route_a_core_side_arbiter" or by["r2_to_delivery_resolution"].get("consumer")!="route_a_typed_delivery_router": raise RTL2R2IngressDeliveryContextError("R2 delivery resolution route differs")
    if "mismatch/stale/duplicate response is rejected" not in by["router_to_context_resolve"].get("rule",""): raise RTL2R2IngressDeliveryContextError("stale response exclusion missing")
    invariants=set(_strings(m,"invariants"))
    if not any("ready-low" in x for x in invariants) or not any("descriptor maintenance" in x for x in invariants): raise RTL2R2IngressDeliveryContextError("ready-low or descriptor invariant missing")
    follow=_object(m,"required_follow_on")
    if follow.get("behavioral_phase")!="rtl2_1b_then_rtl2_2" or "context-registry" not in str(follow.get("requires")): raise RTL2R2IngressDeliveryContextError("follow-on phase differs")
def _object(x:dict[str,Any],k:str)->dict[str,Any]:
    v=x.get(k)
    if not isinstance(v,dict): raise RTL2R2IngressDeliveryContextError(f"{k} must be object")
    return v
def _records(x:dict[str,Any],k:str)->list[dict[str,Any]]:
    v=x.get(k)
    if not isinstance(v,list) or not all(isinstance(i,dict) for i in v): raise RTL2R2IngressDeliveryContextError(f"{k} must be object list")
    return v
def _strings(x:dict[str,Any],k:str)->list[str]:
    v=x.get(k)
    if not isinstance(v,list) or not v or not all(isinstance(i,str) and i for i in v): raise RTL2R2IngressDeliveryContextError(f"{k} must be string list")
    return v
def _ids(rows:list[dict[str,Any]],k:str)->frozenset[str]:
    values=[x.get(k) for x in rows]
    if not all(isinstance(v,str) and v for v in values) or len(values)!=len(set(values)): raise RTL2R2IngressDeliveryContextError(f"{k} missing or duplicate")
    return frozenset(values)
