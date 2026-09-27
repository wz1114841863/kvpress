from tools.analyze_kvzap_route_a4135_target_payload_service_cost import (
    PAGE_BEATS,
    PAGE_BYTES,
    SIDECAR_BYTES,
    hbm_service,
    source_buffer_model,
)


COMMON = {
    "modeled_hbm_transfer_transaction_bytes": 64,
    "read_startup_model_cycles_per_request": 32,
    "write_startup_model_cycles_per_declared_p3_batch": 32,
    "hbm_read_energy_pj_per_byte": 8.0,
    "hbm_write_energy_pj_per_byte": 10.0,
    "source_buffer_consumer_internal_256B_beats_per_model_cycle": 1,
}
PRIMARY = {"profile_id": "primary_256B_per_model_cycle", "sustained_modeled_hbm_transfer_transactions_per_cycle": 4}
SLOW = {"profile_id": "sensitivity_128B_per_model_cycle", "sustained_modeled_hbm_transfer_transactions_per_cycle": 2}
MACRO = {"aggregate_data_array_area_mm2": 0.01, "per_instance_cacti_proxy": {"dynamic_read_energy_pj": 2.0, "dynamic_write_energy_pj": 3.0}}


def test_profile_transaction_service_and_energy_are_explicit():
    read = hbm_service(PAGE_BYTES, 1, PRIMARY, COMMON)
    write = hbm_service(SIDECAR_BYTES, 1, PRIMARY, COMMON, write=True)
    assert read["modeled_transfer_transactions"] == PAGE_BYTES // 64
    assert read["modeled_service_cycles"] == 32 + PAGE_BYTES // (64 * 4)
    assert write["declared_dynamic_energy_pj"] == SIDECAR_BYTES * 10.0


def test_s2_overlap_is_conditioned_on_fill_and_consume_not_assumed():
    primary = source_buffer_model(3, MACRO, PRIMARY, COMMON, "S2_two_32KiB_ping_pong_page_source_buffers")
    slow = source_buffer_model(3, MACRO, SLOW, COMMON, "S2_two_32KiB_ping_pong_page_source_buffers")
    assert primary["per_page_T_consume_model_cycles"] == PAGE_BEATS
    assert primary["per_page_T_fill_model_cycles"] == 32 + (PAGE_BYTES + SIDECAR_BYTES) // (64 * 4)
    assert primary["condition_holds_under_profile"] is False
    assert slow["modeled_consumer_fill_stall_cycles"] > primary["modeled_consumer_fill_stall_cycles"]


def test_source_buffer_multicast_charges_one_read_per_beat_not_four():
    s1 = source_buffer_model(2, MACRO, PRIMARY, COMMON, "S1_one_32KiB_page_source_buffer")
    assert s1["payload_fill_write_accesses"] == 2 * PAGE_BEATS
    assert s1["multicast_payload_read_accesses"] == 2 * PAGE_BEATS
    assert s1["estimated_cacti_source_buffer_dynamic_energy_pj"] == 2 * PAGE_BEATS * (2.0 + 3.0)
