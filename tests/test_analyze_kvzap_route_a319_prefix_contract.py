from tools.analyze_kvzap_route_a319_prefix_contract import common_observed_requirement, suffix_requirement
def test_suffix_requirement_requires_every_later_endpoint_nonnegative():
 assert suffix_requirement([-0.2,0.1,-0.1,0.3])==4
 assert suffix_requirement([-0.2,0.1,0.2,0.3])==2
 assert suffix_requirement([-0.2,-0.1]) is None

def test_common_requirement_does_not_extrapolate_beyond_shortest_trace():
 assert common_observed_requirement([22,15,9],[127,127,91])==22
 assert common_observed_requirement([103,15,9],[127,127,91]) is None
