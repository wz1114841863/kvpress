from tools.analyze_kvzap_route_a4631_attention_admission_contention import COSTS
def test_a4631_cost_profiles_keep_payload_baseline_and_named_metadata_terms():
 assert COSTS['payload_only']['merge']==0
 assert COSTS['metadata_merge_sensitive']['position']==1
