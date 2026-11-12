"""Cross-frontend semantic evidence and comparator-bound projections.

This describes recorded boundaries; it is not a shared hardware contract.
"""
from __future__ import annotations

from typing import Any

VALUE_STATUSES = frozenset({"observed", "derived", "modeled", "unknown", "not_applicable"})

CORE_FIELD_TYPES = {
    "model_topology": {"value_type": "object", "scope": "model-level; model ID/revision, layer count, KV-head count, and query-to-KV grouping when available"},
    "identity": {"value_type": "object", "scope": "(layer, kv_head, source_record_id), with source_record_id kind explicitly labeled"},
    "epoch": {"value_type": "object", "scope": "phase, event kind, forward/decode index, and q_len when available"},
    "decision": {"value_type": "object", "scope": "decision value plus known and effective epochs; unobserved timing stays unknown"},
    "visibility": {"value_type": "object", "scope": "whether a record must be attention-visible at an epoch, distinct from physical completion"},
    "position_provenance": {"value_type": "object", "scope": "literal original logical position, explicit serial, or explicit unknown; never inferred from a slot ID"},
    "traversal_order": {"value_type": "object", "scope": "required source traversal order and the evidence/reason that constrains it"},
    "attention_binding": {"value_type": "object", "scope": "query/KV grouping and the frontend-specific accepted semantic comparator"},
}

REALIZATION_EXTENSIONS = {
    "persistent_packed": {"applies_to": "KVzap Route-A", "extension_only_fields": ["hot_pending_packed_state", "maturity", "admission_service", "append_only_pages", "page_sealing_and_tail"]},
    "one_shot_packed": {"applies_to": "SnapKV P0-P3 mapping", "extension_only_fields": ["terminal_action", "protected_observation_suffix", "canonical_static_packed_state", "initial_compaction"]},
    "dynamic_resident_slot": {"applies_to": "official DMS M0-M4", "extension_only_fields": ["active_slot", "delayed_eviction", "reclaim_reuse", "slot_to_arrival_identity", "native_slot_block_traversal"]},
}

def field(status: str, statement: str, *, reason: str | None = None, subfields: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"status": status, "statement": statement}
    if reason is not None:
        item["reason"] = reason
    if subfields is not None:
        item["subfields"] = subfields
    return item

def availability_matrix() -> dict[str, Any]:
    return {
        "kvzap_route_a_persistent_packed": {
            "frontend": "KVzap Route-A", "realization_extension": "persistent_packed",
            "evidence_scope": "Qwen core closure plus separate Qwen/Llama fixed-horizon coverage; model rows remain separate",
            "fields": {
                "model_topology": field("observed", "Model-specific descriptors are recorded without pooling Qwen and Llama values."),
                "identity": field("observed", "Layer, KV-head, and original-position source identities are preserved by Route-A lifecycle evidence."),
                "epoch": field("observed", "Creation, hot-window, maturity, pending, and packed-cold lifecycle epochs are explicitly represented."),
                "decision": field("observed", "Original KVzap decision semantics and maturity handling are bound by the core closure."),
                "visibility": field("observed", "Policy-on hot, pending, and packed pages are functionally attention-visible under the accepted comparator."),
                "position_provenance": field("observed", "Original positions and append order are preserved by the same-mask reference."),
                "traversal_order": field("observed", "The accepted reference preserves original mask, position, append order, hot window, and online-softmax composition."),
                "attention_binding": field("observed", "Online same-mask dense is the semantic comparator; Full-KV bypass remains a separate control."),
            },
        },
        "snapkv_one_shot_packed": {
            "frontend": "SnapKV", "realization_extension": "one_shot_packed",
            "evidence_scope": "Qwen3-8B terminal-prefill P2/P3 mapping and bounded prefill-tail same-mask probe only",
            "fields": {
                "model_topology": field("derived", "The P2 artifact is archived as a Qwen3-8B fixed-model study; it must not contribute a pooled hardware dimension."),
                "identity": field("observed", "One terminal prefill action is recorded per layer/KV-head/original-position identity."),
                "epoch": field("observed", "Only the terminal prefill epoch is observed.", subfields={"generated_decode_epoch": {"status": "unknown", "reason": "P2 records generated-token/decode continuation as unavailable/null."}}),
                "decision": field("observed", "Terminal retained/dropped action is observed at prefill completion.", subfields={"online_known_or_effective_epoch": {"status": "unknown", "reason": "No online decision/maturity event is observed in P2."}}),
                "visibility": field("derived", "Bounded same-mask prefill-tail visibility is supported by the P2 semantic probe, not native SnapKV decode behavior.", subfields={"generated_decode_visibility": {"status": "unknown", "reason": "Native SnapKV decode/cache semantics were deliberately excluded."}}),
                "position_provenance": field("observed", "Canonical original-position mapping and protected suffix mapping are recorded."),
                "traversal_order": field("observed", "Canonical original-position order is the static packed mapping order; it is not asserted as a native decode traversal."),
                "attention_binding": field("observed", "Same-mask prefill-tail is the accepted bounded comparator.", subfields={"native_decode_comparator": {"status": "unknown", "reason": "No native SnapKV decode claim is supported."}}),
            },
        },
        "official_dms_dynamic_resident_slot": {
            "frontend": "official DMS", "realization_extension": "dynamic_resident_slot",
            "evidence_scope": "Qwen3-8B official DMS M0-M4 fixed decode contract",
            "fields": {
                "model_topology": field("observed", "The all-36-layer native DMS replay records the workload/model binding and observed query-to-KV grouping."),
                "identity": field("observed", "Source arrival serial is observed as the source-record identity; it is not relabeled as a literal token position."),
                "epoch": field("observed", "The fixed decode contract observes delayed controller events and active-resident attention replay."),
                "decision": field("observed", "Delayed eviction/reuse controller behavior is provenance-bound through M1-M3 and replayed in M4."),
                "visibility": field("observed", "The native active resident set is functionally replayed as one attention source under the accepted contract."),
                "position_provenance": field("unknown", "Literal original token position is unavailable.", reason="A generally captured literal original token-position field is absent; only arrival serial and required native order are available."),
                "traversal_order": field("observed", "Required native logical-slot/block-table traversal order is observed; nonmonotonic layer/KV-head orders preclude substituting arrival order."),
                "attention_binding": field("observed", "Unchanged official native DMS FlashAttention is compared with one-source active-resident FP32 replay."),
            },
        },
    }

def validate_matrix(matrix: dict[str, Any]) -> None:
    if any(set(frontend.get("fields", {})) != set(CORE_FIELD_TYPES) for frontend in matrix.values()):
        raise ValueError("C1 every frontend must provide exactly the typed v1 core fields")
    for frontend_name, frontend in matrix.items():
        if frontend.get("realization_extension") not in REALIZATION_EXTENSIONS:
            raise ValueError(f"C1 {frontend_name} names an unknown realization extension")
        for name, item in frontend["fields"].items():
            if item.get("status") not in VALUE_STATUSES:
                raise ValueError(f"C1 {frontend_name}.{name} has invalid status")
            if item["status"] in {"unknown", "not_applicable"} and not item.get("reason"):
                raise ValueError(f"C1 {frontend_name}.{name} requires a reason for {item['status']}")
            for subfield_name, subfield in item.get("subfields", {}).items():
                if subfield.get("status") not in VALUE_STATUSES:
                    raise ValueError(f"C1 {frontend_name}.{name}.{subfield_name} has invalid status")
                if subfield["status"] in {"unknown", "not_applicable"} and not subfield.get("reason"):
                    raise ValueError(f"C1 {frontend_name}.{name}.{subfield_name} requires a reason for {subfield['status']}")

CORE_FIELDS = (
    "model_topology",
    "identity",
    "epoch",
    "decision",
    "visibility",
    "position_provenance",
    "traversal_order",
    "attention_binding",
)

FRONTENDS = (
    "kvzap_route_a_persistent_packed",
    "snapkv_one_shot_packed",
    "official_dms_dynamic_resident_slot",
)

def field_matrix(c2: dict[str, Any]) -> dict[str, dict[str, Any]]:
    projections = c2.get("projections")
    if not isinstance(projections, dict) or set(projections) != set(FRONTENDS):
        raise ValueError("C3 requires exactly three C2 frontend projections")
    rows: dict[str, dict[str, Any]] = {}
    for field_name in CORE_FIELDS:
        cells: dict[str, Any] = {}
        for frontend in FRONTENDS:
            projection = projections[frontend]
            core = projection.get("core_fields") if isinstance(projection, dict) else None
            item = core.get(field_name) if isinstance(core, dict) else None
            if not isinstance(item, dict) or item.get("status") not in {"observed", "derived", "modeled", "unknown", "not_applicable"}:
                raise ValueError(f"C3 missing typed C2 field {frontend}.{field_name}")
            cells[frontend] = {"status": item["status"], "reason": item.get("reason"), "value": item.get("value")}
        statuses = {name: item["status"] for name, item in cells.items()}
        rows[field_name] = {
            "per_frontend": cells,
            "all_observed": all(status == "observed" for status in statuses.values()),
            "all_available": all(status in {"observed", "derived"} for status in statuses.values()),
            "statuses": statuses,
        }
    return rows

def invariant_candidates(matrix: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        {
            "name": "explicit_source_record_identity",
            "required_fields": ["identity"],
            "common_abstraction": "Every evaluated frontend exposes an explicit source_record_id associated with layer and KV head.",
            "non_invariant_detail": "KVzap/SnapKV use original logical positions; DMS uses an arrival serial, not a literal position.",
        },
        {
            "name": "explicit_epoch_and_decision_scope",
            "required_fields": ["epoch", "decision"],
            "common_abstraction": "Every evaluated frontend binds its retained/active control semantics to an explicit scope or epoch.",
            "non_invariant_detail": "KVzap has lifecycle/maturity, SnapKV only terminal prefill, and DMS a fixed decode controller contract; no common online timeline is inferred.",
        },
        {
            "name": "required_frontend_specific_traversal_order",
            "required_fields": ["traversal_order"],
            "common_abstraction": "Attention realization must preserve the frontend-specified source traversal order.",
            "non_invariant_detail": "This does not define one canonical order: DMS native slot/block order cannot be replaced by arrival order.",
        },
        {
            "name": "frontend_bound_semantic_comparator",
            "required_fields": ["attention_binding"],
            "common_abstraction": "Each frontend requires an explicit accepted semantic comparator for any later attention study.",
            "non_invariant_detail": "Comparators are distinct: KVzap same-mask dense, SnapKV prefill-tail, and DMS native FlashAttention replay.",
        },
    ]
    accepted: list[dict[str, Any]] = []
    for candidate in candidates:
        if all(matrix[field]["all_observed"] for field in candidate["required_fields"]):
            accepted.append(candidate)
    return accepted

def frontend_specific(c2: dict[str, Any]) -> list[dict[str, Any]]:
    projections = c2["projections"]
    return [
        {
            "frontend": "kvzap_route_a_persistent_packed",
            "realization_extension": projections["kvzap_route_a_persistent_packed"]["realization_extension"],
            "specific_mechanisms": ["hot/pending/packed lifecycle", "maturity and admission", "optional multi-source partial composition with one online-softmax merge"],
            "boundary": "These are KVzap Route-A realization mechanisms, not common C3 interface fields.",
        },
        {
            "frontend": "snapkv_one_shot_packed",
            "realization_extension": projections["snapkv_one_shot_packed"]["realization_extension"],
            "specific_mechanisms": ["terminal prefill action", "protected observation suffix compatibility mapping", "canonical static original-position packing"],
            "boundary": "No generated decode, online maturity, or native decode/cache semantics are observed.",
        },
        {
            "frontend": "official_dms_dynamic_resident_slot",
            "realization_extension": projections["official_dms_dynamic_resident_slot"]["realization_extension"],
            "specific_mechanisms": ["dynamic active slots", "delayed eviction/reuse", "required native logical-slot/block-table traversal"],
            "boundary": "DMS is not asserted to be a packed-cold source and its native order is not an order-invariance result.",
        },
    ]

def unresolved(matrix: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    unresolved_rows = [
        {
            "name": "literal_dms_original_position",
            "affected_field": "position_provenance",
            "reason": matrix["position_provenance"]["per_frontend"]["official_dms_dynamic_resident_slot"]["reason"],
        },
        {
            "name": "snapkv_generated_decode_and_online_lifecycle",
            "affected_fields": ["epoch", "decision", "visibility", "attention_binding"],
            "reason": "C2 retains terminal-prefill scope only; generated decode, maturity timing, native decode visibility, and native decode comparator remain unknown.",
        },
        {
            "name": "shared_physical_or_temporal_resource_contract",
            "affected_fields": ["all"],
            "reason": "No common source-ready/completion order, queue/backpressure, allocator, capacity, traffic, timing, or hardware interface is established by C0-C3.",
        },
        {
            "name": "universal_multi_source_composition",
            "affected_fields": ["visibility", "traversal_order"],
            "reason": "KVzap has accepted hot/pending/packed composition; SnapKV and DMS must not be artificially partitioned into sources.",
        },
    ]
    return unresolved_rows

def validate_analysis(matrix: dict[str, dict[str, Any]], invariants: list[dict[str, Any]], unresolved_rows: list[dict[str, Any]]) -> None:
    for candidate in invariants:
        if not all(matrix[field]["all_observed"] for field in candidate["required_fields"]):
            raise ValueError(f"C3 invariant {candidate['name']} lacks all-observed prerequisite")
    if matrix["position_provenance"]["all_observed"]:
        raise ValueError("C3 must not erase the DMS position-provenance unknown")
    if not any(row["name"] == "snapkv_generated_decode_and_online_lifecycle" for row in unresolved_rows):
        raise ValueError("C3 must retain SnapKV decode/lifecycle as unresolved")

def analyze_projections(c2: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Classify observed common fields without changing frontend semantics."""
    matrix = field_matrix(c2)
    invariants = invariant_candidates(matrix)
    specific = frontend_specific(c2)
    unresolved_rows = unresolved(matrix)
    validate_analysis(matrix, invariants, unresolved_rows)
    return matrix, invariants, specific, unresolved_rows

def projected_field(status: str, value: Any = None, *, reason: str | None = None, evidence: list[str]) -> dict[str, Any]:
    item: dict[str, Any] = {"status": status, "evidence_sources": evidence}
    if status in {"unknown", "not_applicable"}:
        if reason is None:
            raise ValueError(f"C2 {status} projection requires a reason")
        item["reason"] = reason
        item["value"] = None
    else:
        item["value"] = value
    return item

def c1_status(c1: dict[str, Any], frontend: str, field_name: str) -> str:
    try:
        status = c1["frontend_field_availability"][frontend]["fields"][field_name]["status"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"C2 C1 availability lacks {frontend}.{field_name}") from error
    if status not in VALUE_STATUSES:
        raise ValueError(f"C2 C1 has invalid availability status for {frontend}.{field_name}")
    return status

def require_qwen_shape(qwen: dict[str, Any], m6: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    descriptor = qwen.get("qwen3_8b_kvzap_resource_descriptor")
    core = qwen.get("route_a_core_contract_v1")
    per_model = m6.get("per_model_fixed_workload_descriptors")
    if not isinstance(descriptor, dict) or not isinstance(core, dict) or not isinstance(per_model, dict):
        raise ValueError("C2 KVzap sources lack required core/coverage descriptors")
    scope = descriptor.get("scope")
    if not isinstance(scope, dict) or scope.get("model") != "Qwen/Qwen3-8B" or scope.get("observed_layer_count") != 36 or scope.get("observed_kv_head_count") != 288:
        raise ValueError("C2 KVzap Qwen source does not expose the expected semantic topology")
    if not isinstance(per_model.get("qwen3_8b_kvzap"), list) or not isinstance(per_model.get("nous_llama31_8b_kvzap"), list):
        raise ValueError("C2 KVzap coverage must retain separate Qwen and Llama rows")
    return descriptor, scope, core

def snap_statuses(snap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    descriptor = snap.get("descriptor")
    rows = descriptor.get("field_statuses") if isinstance(descriptor, dict) else None
    if not isinstance(rows, list):
        raise ValueError("C2 SnapKV source lacks field-status rows")
    by_name = {row.get("name"): row for row in rows if isinstance(row, dict)}
    required = ("terminal_per_identity_action", "canonical_identity_and_append_order", "online_decision_epochs_and_maturity_events", "generated_token_decision_and_decode_continuation")
    if any(by_name.get(name, {}).get("status") not in {"available", "unavailable"} for name in required):
        raise ValueError("C2 SnapKV source has incomplete terminal/decode boundary")
    if by_name["generated_token_decision_and_decode_continuation"].get("value") is not None:
        raise ValueError("C2 SnapKV generated decode must remain null")
    return by_name

def require_dms_shape(dms: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    active = dms.get("active_resident_attention")
    topology = dms.get("fresh_native_control_topology")
    if not isinstance(active, dict) or not isinstance(topology, dict):
        raise ValueError("C2 DMS source lacks active-resident/topology evidence")
    if active.get("all_36_layers_all_decode_steps_observed") is not True or topology.get("final_active_physical_slot_order_nonmonotonic_count") != 269:
        raise ValueError("C2 DMS source does not preserve all-layer/nonmonotonic-order boundary")
    return active, topology

def build_kvzap_projection(c1: dict[str, Any], qwen: dict[str, Any], m6: dict[str, Any]) -> dict[str, Any]:
    frontend = "kvzap_route_a_persistent_packed"
    descriptor, scope, core = require_qwen_shape(qwen, m6)
    lifecycle = core["lifecycle"]
    attention = core["attention"]
    dependency = core["dependency"]
    return {
        "frontend": frontend,
        "realization_extension": "persistent_packed",
        "model_anchors": {
            "qwen3_8b": {"model": scope["model"], "model_revision": scope["model_revision"], "layer_count": scope["observed_layer_count"], "kv_head_count": scope["observed_kv_head_count"], "query_heads_per_kv_head_group": descriptor["qwen_specific_group_width_values"]},
            "llama31_8b": {"status": "observed_separate_coverage", "reason": "M6 supplies separate normalized rows; C2 does not pool them with Qwen or infer an identical topology."},
        },
        "core_fields": {
            "model_topology": projected_field(c1_status(c1, frontend, "model_topology"), {"topology_scope": "model-specific; Qwen and Llama rows remain separate", "qwen": scope}, evidence=["kvzap_qwen_core_contract", "kvzap_qwen_llama_coverage"]),
            "identity": projected_field(c1_status(c1, frontend, "identity"), {"source_record_id_kind": "original_logical_position", "keying": "(layer, kv_head, original_logical_position)"}, evidence=["kvzap_qwen_core_contract"]),
            "epoch": projected_field(c1_status(c1, frontend, "epoch"), {"lifecycle": ["creation", "hot_window", "maturity", "pending_staging", "sealed_packed_cold"], "source_statement": lifecycle}, evidence=["kvzap_qwen_core_contract"]),
            "decision": projected_field(c1_status(c1, frontend, "decision"), {"retain_drop": "original KVzap decision available no later than maturity", "source_statement": lifecycle[0]}, evidence=["kvzap_qwen_core_contract"]),
            "visibility": projected_field(c1_status(c1, frontend, "visibility"), {"active_sources": ["hot", "pending", "packed"], "semantic_scope": "policy-on functional reference"}, evidence=["kvzap_qwen_core_contract"]),
            "position_provenance": projected_field(c1_status(c1, frontend, "position_provenance"), {"position_kind": "original_logical_position", "append_order_preserved": True}, evidence=["kvzap_qwen_core_contract"]),
            "traversal_order": projected_field(c1_status(c1, frontend, "traversal_order"), {"source_order_contract": "ordered hot/pending/packed partial-or-skip decisions, then one merge", "cross_layer_order_preserved": True, "source_statement": dependency}, evidence=["kvzap_qwen_core_contract"]),
            "attention_binding": projected_field(c1_status(c1, frontend, "attention_binding"), {"comparator": "online same-mask dense; Full-KV bypass distinct", "source_statement": attention, "query_to_kv_group_relation": "model-scoped, not an accelerator dimension"}, evidence=["kvzap_qwen_core_contract"]),
        },
        "realization_extension_fields": {"hot_pending_packed_lifecycle": "applicable", "page_or_tail_values": "frontend-specific trace-derived fields; not exported as common core", "online_softmax_merge": "KVzap-specific accepted functional composition"},
    }

def build_snap_projection(c1: dict[str, Any], snap: dict[str, Any]) -> dict[str, Any]:
    frontend = "snapkv_one_shot_packed"
    rows = snap_statuses(snap)
    source = snap["source"]
    terminal = rows["terminal_per_identity_action"]["value"]
    return {
        "frontend": frontend,
        "realization_extension": "one_shot_packed",
        "model_anchors": {"qwen3_8b": {"status": "derived", "reason": "P2 is a fixed Qwen3-8B study; no pooled topology or hardware dimension is created."}},
        "core_fields": {
            "model_topology": projected_field(c1_status(c1, frontend, "model_topology"), {"scope": "fixed Qwen3-8B P2 study only"}, evidence=["snapkv_terminal_prefill"]),
            "identity": projected_field(c1_status(c1, frontend, "identity"), {"source_record_id_kind": "original_logical_position", "keying": "(layer, kv_head, original_logical_position)", "terminal_event_count": terminal["event_count"]}, evidence=["snapkv_terminal_prefill"]),
            "epoch": projected_field(c1_status(c1, frontend, "epoch"), {"observed_epoch": source["p0_decision_epoch"], "generated_decode_epoch": None}, evidence=["snapkv_terminal_prefill"]),
            "decision": projected_field(c1_status(c1, frontend, "decision"), {"decision_kind": "terminal prefill retain/drop", "known_epoch": terminal["decision_epoch"], "online_effective_epoch": None}, evidence=["snapkv_terminal_prefill"]),
            "visibility": projected_field(c1_status(c1, frontend, "visibility"), {"supported_scope": "bounded same-mask prefill-tail probe", "generated_decode_visibility": None}, evidence=["snapkv_terminal_prefill"]),
            "position_provenance": projected_field(c1_status(c1, frontend, "position_provenance"), {"position_kind": "original_logical_position", "protected_suffix_mapping": "recorded only for the compatibility mapping"}, evidence=["snapkv_terminal_prefill"]),
            "traversal_order": projected_field(c1_status(c1, frontend, "traversal_order"), {"order": "canonical original-position order per (layer, KV head)", "excluded": "native score-ranked gather order"}, evidence=["snapkv_terminal_prefill"]),
            "attention_binding": projected_field(c1_status(c1, frontend, "attention_binding"), {"comparator": "same-mask prefill-tail", "native_decode_comparator": None}, evidence=["snapkv_terminal_prefill"]),
        },
        "unknown_subfields": {
            "generated_decode_epoch": "P2 records generated-token/decode continuation as unavailable/null.",
            "online_decision_or_maturity_epoch": "P2 records no online decision epochs or maturity events.",
            "native_decode_visibility_and_comparator": "Native SnapKV cache/decode semantics are deliberately excluded.",
        },
        "realization_extension_fields": {"terminal_action": "applicable", "protected_observation_suffix": "applicable only to the P0-P3 compatibility mapping", "pending_or_decode_lifecycle": "unknown, not zero"},
    }

def build_dms_projection(c1: dict[str, Any], dms: dict[str, Any]) -> dict[str, Any]:
    frontend = "official_dms_dynamic_resident_slot"
    active, topology = require_dms_shape(dms)
    return {
        "frontend": frontend,
        "realization_extension": "dynamic_resident_slot",
        "model_anchors": {"qwen3_8b": {"status": "observed", "layer_coverage": 36, "query_heads_per_kv_head_group_values": active["query_heads_per_kv_head_group_values"], "head_dim_values": active["head_dim_values"], "scope": "fixed official DMS decode contract"}},
        "core_fields": {
            "model_topology": projected_field(c1_status(c1, frontend, "model_topology"), {"layer_coverage": 36, "query_heads_per_kv_head_group_values": active["query_heads_per_kv_head_group_values"], "head_dim_values": active["head_dim_values"]}, evidence=["official_dms_active_resident"]),
            "identity": projected_field(c1_status(c1, frontend, "identity"), {"source_record_id_kind": "source_arrival_serial", "literal_original_token_position": None}, evidence=["official_dms_active_resident"]),
            "epoch": projected_field(c1_status(c1, frontend, "epoch"), {"phase": "fixed decode contract", "decode_flash_attention_call_count": active["decode_flash_attention_call_count"]}, evidence=["official_dms_active_resident"]),
            "decision": projected_field(c1_status(c1, frontend, "decision"), {"controller": "delayed eviction/reuse", "provenance": "M1-M3 bound and replayed in M4"}, evidence=["official_dms_active_resident"]),
            "visibility": projected_field(c1_status(c1, frontend, "visibility"), {"source": "native active resident set", "semantic_scope": "one-source functional replay"}, evidence=["official_dms_active_resident"]),
            "position_provenance": projected_field(c1_status(c1, frontend, "position_provenance"), reason="No generally captured literal original token-position field exists; arrival serial and required native order remain distinct.", evidence=["official_dms_active_resident"]),
            "traversal_order": projected_field(c1_status(c1, frontend, "traversal_order"), {"order": "official native logical-slot/block-table order", "nonmonotonic_layer_kv_head_orders": topology["final_active_physical_slot_order_nonmonotonic_count"], "arrival_order_substitution": "forbidden"}, evidence=["official_dms_active_resident"]),
            "attention_binding": projected_field(c1_status(c1, frontend, "attention_binding"), {"comparator": "unchanged official native DMS FlashAttention versus one-source active-resident FP32 replay", "tolerance_scope": "fixed contract only"}, evidence=["official_dms_active_resident"]),
        },
        "realization_extension_fields": {"active_slot": "applicable", "delayed_eviction_and_reuse": "applicable", "native_slot_block_traversal": "required", "packed_cold_mapping": "not established"},
    }

def validate_projection(c1: dict[str, Any], projection: dict[str, Any]) -> None:
    frontend = projection.get("frontend")
    if frontend not in FRONTENDS or projection.get("realization_extension") not in {"persistent_packed", "one_shot_packed", "dynamic_resident_slot"}:
        raise ValueError("C2 projection has unknown frontend/extension")
    fields = projection.get("core_fields")
    if not isinstance(fields, dict) or set(fields) != set(CORE_FIELDS):
        raise ValueError(f"C2 {frontend} must project exactly the v1 core fields")
    for field_name, item in fields.items():
        expected = c1_status(c1, frontend, field_name)
        if item.get("status") != expected:
            raise ValueError(f"C2 {frontend}.{field_name} changed C1 status {expected!r} to {item.get('status')!r}")
        if not item.get("evidence_sources"):
            raise ValueError(f"C2 {frontend}.{field_name} lacks evidence_sources")
        if expected in {"unknown", "not_applicable"}:
            if item.get("value") is not None or not item.get("reason"):
                raise ValueError(f"C2 {frontend}.{field_name} fabricated or unexplained unavailable value")

def snap_field_rows(snap: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = snap.get("descriptor", {}).get("field_statuses")
    if not isinstance(rows, list):
        raise ValueError("C4 SnapKV P2 lacks field statuses")
    values = {row.get("name"): row for row in rows if isinstance(row, dict)}
    semantic = values.get("same_mask_prefill_tail_semantics")
    generated = values.get("generated_token_decision_and_decode_continuation")
    if semantic is None or semantic.get("status") != "available":
        raise ValueError("C4 SnapKV same-mask prefill-tail functional evidence is absent")
    if generated is None or generated.get("status") != "unavailable" or generated.get("value") is not None:
        raise ValueError("C4 SnapKV generated decode must remain unavailable/null")
    return values

def build_kvzap(qwen: dict[str, Any]) -> dict[str, Any]:
    core = qwen.get("route_a_core_contract_v1")
    attention = core.get("attention") if isinstance(core, dict) else None
    data_plane = core.get("data_plane_interfaces") if isinstance(core, dict) else None
    if not isinstance(attention, list) or not isinstance(data_plane, list):
        raise ValueError("C4 KVzap core lacks attention/data-plane contract")
    required_sources = {"hot_source", "pending_retained_cold_staging", "sealed_packed_cold_pages", "online_softmax_merge"}
    names = {row.get("name") for row in data_plane if isinstance(row, dict)}
    if not required_sources.issubset(names) or not any("Same-mask dense" in line for line in attention):
        raise ValueError("C4 KVzap functional traversal comparator is incomplete")
    return {
        "frontend": "kvzap_route_a_persistent_packed",
        "source_cardinality": {"minimum": 1, "maximum": 3, "rule": "hot, pending, and packed each produce an ordered partial or explicit empty outcome; no source must be fabricated."},
        "source_traversal": {"order": ["hot", "pending", "packed"], "empty_source_behavior": "explicit partial-or-skip", "merge": "exactly one online-softmax merge after source decisions"},
        "semantic_comparator": {"accepted_comparator": "online same-mask dense", "separate_control": "Full-KV bypass", "evidence_classification": "previously accepted functional reference; C4 rechecks manifest assertions only"},
        "c4_primitive_fit": "supports ordered variable-length source traversal with optional multi-source composition",
        "boundary": "C4 does not select split/co-located placement, scheduler, merge precision, page layout, or physical source implementation.",
    }

def build_snap(snap: dict[str, Any]) -> dict[str, Any]:
    fields = snap_field_rows(snap)
    canonical = fields.get("canonical_identity_and_append_order")
    if canonical is None or canonical.get("status") != "available":
        raise ValueError("C4 SnapKV canonical traversal mapping is absent")
    return {
        "frontend": "snapkv_one_shot_packed",
        "source_cardinality": {"minimum": 1, "maximum": 1, "rule": "one canonical terminal-prefill source; no artificial hot/pending/packed decomposition"},
        "source_traversal": {"order": "canonical original-position order per (layer, KV head)", "excluded_order": "native score-ranked gather order", "merge": "not required by the bounded one-source probe"},
        "semantic_comparator": {"accepted_comparator": "same-mask prefill-tail", "decode_scope": "not established", "evidence_classification": "previously accepted bounded functional probe; C4 rechecks P2/P3 summary only"},
        "c4_primitive_fit": "supports a single ordered variable-length source for the bounded prefill-tail scope",
        "boundary": "No generated decode, online lifecycle, native SnapKV cache/decode traversal, or multi-source requirement is inferred.",
    }

def build_dms(dms: dict[str, Any]) -> dict[str, Any]:
    guards = dms.get("observational_guards")
    active = dms.get("active_resident_attention")
    topology = dms.get("fresh_native_control_topology")
    if not isinstance(guards, dict) or not isinstance(active, dict) or not isinstance(topology, dict):
        raise ValueError("C4 DMS M4 lacks guard/active/topology objects")
    if guards.get("native_dms_cache_used") is not True or guards.get("attention_replaced") is not False or active.get("all_active_resident_replays_within_declared_tolerance") is not True:
        raise ValueError("C4 DMS native active-resident comparator is incomplete")
    if topology.get("final_active_physical_slot_order_nonmonotonic_count") != 269:
        raise ValueError("C4 DMS required native-order boundary drifted")
    return {
        "frontend": "official_dms_dynamic_resident_slot",
        "source_cardinality": {"minimum": 1, "maximum": 1, "rule": "one native active-resident source; no artificial partition or packed-cold mapping"},
        "source_traversal": {"order": "official native logical-slot/block-table order", "arrival_order_substitution": "forbidden", "nonmonotonic_layer_kv_head_orders": 269, "merge": "not required by the one-source replay"},
        "semantic_comparator": {"accepted_comparator": "unchanged official native DMS FlashAttention versus one-source active-resident FP32 replay", "scope": "fixed decode contract", "evidence_classification": "previously accepted functional replay; C4 rechecks M4 guard/summary only"},
        "c4_primitive_fit": "supports a single ordered variable-length active-resident source only when native traversal order is preserved",
        "boundary": "Arrival serial is not a literal original token position; C4 does not claim slot-order invariance or a packed-cold realization.",
    }

def validate_reports(reports: dict[str, dict[str, Any]], c3: dict[str, Any]) -> None:
    if set(reports) != {"kvzap_route_a_persistent_packed", "snapkv_one_shot_packed", "official_dms_dynamic_resident_slot"}:
        raise ValueError("C4 must emit exactly three frontend traversal reports")
    for name, report in reports.items():
        card = report.get("source_cardinality")
        comparator = report.get("semantic_comparator")
        traversal = report.get("source_traversal")
        if not isinstance(card, dict) or card.get("minimum") < 1 or card.get("maximum") < card.get("minimum"):
            raise ValueError(f"C4 invalid source cardinality for {name}")
        if not isinstance(comparator, dict) or not comparator.get("accepted_comparator"):
            raise ValueError(f"C4 missing accepted comparator for {name}")
        if not isinstance(traversal, dict) or not traversal.get("order"):
            raise ValueError(f"C4 missing traversal order for {name}")
    if reports["snapkv_one_shot_packed"]["source_cardinality"]["maximum"] != 1 or reports["official_dms_dynamic_resident_slot"]["source_cardinality"]["maximum"] != 1:
        raise ValueError("C4 must not require multi-source composition for SnapKV or DMS")
    if reports["official_dms_dynamic_resident_slot"]["source_traversal"].get("arrival_order_substitution") != "forbidden":
        raise ValueError("C4 must preserve the DMS native-order restriction")
    if not any(row.get("name") == "universal_multi_source_composition" for row in c3.get("unresolved_boundaries", []) if isinstance(row, dict)):
        raise ValueError("C4 must retain C3 multi-source unresolved boundary")

def decide(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    c3 = reports["c3"]
    c4 = reports["c4"]
    specific = {row.get("frontend") for row in c3.get("frontend_specific_mechanisms", []) if isinstance(row, dict)}
    unresolved = {row.get("name") for row in c3.get("unresolved_boundaries", []) if isinstance(row, dict)}
    expected_specific = {"kvzap_route_a_persistent_packed", "snapkv_one_shot_packed", "official_dms_dynamic_resident_slot"}
    expected_unresolved = {"literal_dms_original_position", "snapkv_generated_decode_and_online_lifecycle", "shared_physical_or_temporal_resource_contract", "universal_multi_source_composition"}
    if specific != expected_specific or not expected_unresolved.issubset(unresolved):
        raise ValueError("C5 C3 classification boundary is incomplete")
    summary = c4.get("comparison_summary")
    if not isinstance(summary, dict) or summary.get("candidate_common_primitive") != "frontend-bound ordered variable-length source traversal under each frontend's accepted semantic comparator":
        raise ValueError("C5 C4 candidate common primitive drifted")
    not_established = set(summary.get("not_established", []))
    required_not_established = {"a common cache format", "a common source order", "mandatory multi-source composition", "scheduler/backpressure/temporal resource contract", "allocator/capacity/traffic/timing/hardware interface"}
    if not required_not_established.issubset(not_established):
        raise ValueError("C5 cannot promote a common substrate while C4 boundaries are incomplete")
    return {
        "primary_direction": "route_a_persistent_packed_backend",
        "decision": "retain_as_primary_research_and_architecture_path",
        "decision_basis": [
            "KVzap retains a distinct persistent-packed lifecycle: stable decision, hot window, maturity, pending staging, append-only packed cold state, and optional online-softmax composition.",
            "C3/C4 find only a frontend-bound semantic traversal abstraction, not a common cache format, source order, or mandatory multi-source realization.",
            "SnapKV and DMS are valuable boundary/workload evidence but their observed realizations remain one-shot prefill and dynamic resident-slot respectively.",
        ],
        "candidate_common_substrate": {
            "status": "semantic_abstraction_only_not_selected_as_hardware_direction",
            "abstraction": summary["candidate_common_primitive"],
            "reason": "The three frontends retain incompatible lifecycle/order/comparator details and unresolved physical/temporal contract fields.",
        },
        "cross_frontend_role": {
            "kvzap": "primary backend and architecture differentiation target",
            "snapkv": "one-shot-prefill semantic boundary and future workload-envelope contrast; not a decode lifecycle proof",
            "official_dms": "dynamic-resident decode boundary and native-order preservation contrast; not a packed-cold mapping",
        },
    }

def pre_rtl_checklist() -> list[dict[str, Any]]:
    return [
        {
            "name": "route_a_resource_contract_freeze",
            "required_before_architecture_spec": True,
            "status": "not_selected",
            "need": "Choose FIFO/PTE/page/bank/burst/merge precision/PE/scheduler/controller parameters only from a separately documented Route-A resource study.",
        },
        {
            "name": "route_a_workload_envelope_and_fallback",
            "required_before_architecture_spec": True,
            "status": "partial_existing_evidence_not_final",
            "need": "Keep Qwen/Llama descriptor rows separate, preserve Full-KV bypass, and establish the intended Route-A workload envelope without pooling fixed-request counts into hardware dimensions.",
        },
        {
            "name": "new_frontend_onboarding_rule",
            "required_before_architecture_spec": False,
            "status": "semantic_preconditions_defined",
            "need": "A future frontend must expose a stable decision/active-state semantics, explicit identity/order, and an accepted comparator; otherwise it remains a boundary case rather than a Route-A mapping.",
        },
        {
            "name": "unresolved_cross_frontend_fields",
            "required_before_architecture_spec": False,
            "status": "explicitly_retained",
            "need": "Do not fill SnapKV generated decode, DMS literal position, or common scheduler/backpressure fields merely to create a universal interface.",
        },
        {
            "name": "rtl_authorization",
            "required_before_architecture_spec": True,
            "status": "not_authorized",
            "need": "C5 is a research-direction memo only. A separate architecture-spec gate must freeze parameters and evidence boundaries before RTL.",
        },
    ]

def validate_decision(decision: dict[str, Any], checklist: list[dict[str, Any]]) -> None:
    if decision.get("primary_direction") != "route_a_persistent_packed_backend":
        raise ValueError("C5 only accepts the evidence-supported Route-A primary direction")
    common = decision.get("candidate_common_substrate", {})
    if common.get("status") != "semantic_abstraction_only_not_selected_as_hardware_direction":
        raise ValueError("C5 must not promote a common semantic abstraction into a hardware direction")
    rtl = [row for row in checklist if row.get("name") == "rtl_authorization"]
    if len(rtl) != 1 or rtl[0].get("status") != "not_authorized":
        raise ValueError("C5 must retain the pre-RTL gate")
