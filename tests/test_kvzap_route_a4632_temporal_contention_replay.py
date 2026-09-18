from tools.analyze_kvzap_route_a4630_physicalization_mapping import EAGER_COPY
from tools.analyze_kvzap_route_a4632_temporal_contention_replay import replay


def _variant() -> dict[str, object]:
    return {
        "drain_horizon_append_opportunities": 2,
        "minimum_logical_service_quantum": 4,
        "mapping_assumption": EAGER_COPY,
        "candidate_page_tokens": 16,
    }


def test_a4632_records_the_backlog_recurrence_and_maps_grants():
    inventory = {(0, 0): {"pending": 3, "packed": 1, "hot": 2}}
    arrivals = {(0, 0): [1, 0]}
    result = replay(inventory=inventory, arrivals=arrivals, variant=_variant(), policy="backlog_deadline_aware")
    first = result["epoch_records"][0]
    assert first["B_t_before_arrivals_logical_tokens"] == 3
    assert first["A_t_new_mature_kept_logical_tokens"] == 1
    assert first["B_t_after_arrivals_logical_tokens"] == 4
    assert first["B_t_plus_1_after_grant_logical_tokens"] == 0
    assert first["G_t_logical_admission_grant"] == 4
    assert first["G_t_mapped_admission_work_components"]["modeled_kv_payload_source_read_token_units"] == 4


def test_a4632_work_conserving_lends_empty_reservation_but_hard_does_not():
    inventory = {(0, 0): {"pending": 0, "packed": 1, "hot": 2}}
    arrivals = {(0, 0): [0, 0]}
    hard = replay(inventory=inventory, arrivals=arrivals, variant=_variant(), policy="hard_reservation")
    work_conserving = replay(inventory=inventory, arrivals=arrivals, variant=_variant(), policy="work_conserving_reserved_minimum")
    assert hard["reservation_idle_logical_tokens"] == 2
    assert hard["attention_borrowed_logical_admission_capacity"] == 0
    assert work_conserving["reservation_idle_logical_tokens"] == 0
    assert work_conserving["attention_borrowed_logical_admission_capacity"] == 8


def test_a4632_counts_dual_source_merge_once_per_head_per_opportunity():
    inventory = {(0, 0): {"pending": 3, "packed": 1, "hot": 2}}
    arrivals = {(0, 0): [0, 0]}
    variant = {**_variant(), "minimum_logical_service_quantum": 1}
    result = replay(inventory=inventory, arrivals=arrivals, variant=variant, policy="hard_reservation")
    assert result["post_service_dual_source_merge_state_records"] == 2


def test_a4632_keeps_merge_attention_work_out_of_zero_grant_admission_work():
    inventory = {(0, 0): {"pending": 2, "packed": 1, "hot": 2}}
    arrivals = {(0, 0): [0, 0]}
    result = replay(inventory=inventory, arrivals=arrivals, variant=_variant(), policy="strict_attention_first")
    assert result["attention_service_occupied_by_admission_abstract_work_units"]["metadata_merge_sensitive"] == 0
    assert result["post_service_dual_source_merge_attention_abstract_work_units"]["metadata_merge_sensitive"] == 4
