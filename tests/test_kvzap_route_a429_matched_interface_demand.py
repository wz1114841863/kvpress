from tools.analyze_kvzap_route_a429_matched_interface_demand import summarize

def test_a429_counts_modeled_exports_not_hardware_work():
    event=lambda active: {"layer":0,"kv_head":0,"packed_page_count":2,"packed_tail_tokens":3,"source_decisions":[{"source":s,"outcome":"partial" if s in active else "skip","record_count":4 if s in active else 0} for s in ("hot","pending","packed")]}
    row=summarize([event({"hot","packed"}),event({"hot","pending","packed"})])
    assert row["modeled_split_state_exports"]["total"] == 5
    assert row["modeled_split_state_exports"]["additional_reduction_inputs_total"] == 3
    assert row["modeled_split_state_exports"]["co_located_exports"] == 0
