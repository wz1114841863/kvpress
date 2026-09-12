from tools.analyze_kvzap_route_a4211_partitioned_backpressure_sensitivity import simulate
def test_partitioning_and_parallelism_are_explicit_virtual_axes():
 e=lambda l,h,p:{"layer":l,"kv_head":h,"cache_position":p,"source_decisions":[{"source":"hot","outcome":"partial"},{"source":"packed","outcome":"partial"},{"source":"pending","outcome":"skip"}]}
 es=[e(0,0,1),e(1,0,1)]
 assert simulate(es,"per_layer","sequential","tree_depth",1,1)["modeled_backpressured_tasks"]==0
 assert simulate(es,"global","cache_position_burst","flat",1,1)["modeled_backpressured_tasks"]>0
 assert simulate(es,"global","sequential","flat",2,1) is None
 assert simulate(es,"per_layer","trace_dispatch_epoch","tree_depth",1,1,{0: 0, 1: 1})["modeled_backpressured_tasks"] == 0
