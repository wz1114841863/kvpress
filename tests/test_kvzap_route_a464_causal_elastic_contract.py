from tools.analyze_kvzap_route_a4630_physicalization_mapping import EAGER_COPY
from tools.analyze_kvzap_route_a464_causal_elastic_contract import SERVICE_LEVELS, causal_level, replay


def _variant() -> dict[str, object]:
    return {"drain_horizon_append_opportunities": 3, "mapping_assumption": EAGER_COPY, "candidate_page_tokens": 16}


def test_a464_causal_level_uses_only_current_history_counters():
    state = {"level_index": 0, "quiet_streak": 0}
    level, transition = causal_level(state=state, layer_backlog=513, max_head_backlog=1, age_max=0)
    assert (level, transition) == (1, "escalate")
    level, transition = causal_level(state=state, layer_backlog=1, max_head_backlog=65, age_max=0)
    assert (level, transition) == (2, "escalate")
    assert SERVICE_LEVELS == (16, 64, 256)


def test_a464_future_arrival_mutation_cannot_change_causal_prefix_decision():
    inventory = {(0, 0): {"pending": 20, "packed": 1, "hot": 2}}
    original = {(0, 0): [0, 0, 0]}
    changed_future = {(0, 0): [0, 7, 0]}
    first = replay(inventory=inventory, arrivals=original, variant=_variant(), policy="causal_counter_hysteresis_v1")
    second = replay(inventory=inventory, arrivals=changed_future, variant=_variant(), policy="causal_counter_hysteresis_v1")
    assert first["epoch_records"][0]["layer_controller_observations"] == second["epoch_records"][0]["layer_controller_observations"]
    assert first["epoch_records"][0]["G_t_logical_admission_grant"] == second["epoch_records"][0]["G_t_logical_admission_grant"]


def test_a464_offline_oracle_is_explicitly_distinct_from_causal_policy():
    inventory = {(0, 0): {"pending": 1, "packed": 1, "hot": 2}}
    arrivals = {(0, 0): [0, 0, 300]}
    causal = replay(inventory=inventory, arrivals=arrivals, variant=_variant(), policy="causal_counter_hysteresis_v1")
    oracle = replay(inventory=inventory, arrivals=arrivals, variant=_variant(), policy="same_levels_offline_oracle_reference")
    assert causal["epoch_records"][0]["layer_controller_observations"][0]["service_level"] == "minimum"
    assert oracle["epoch_records"][0]["layer_controller_observations"][0]["transition"] == "offline_reference"
