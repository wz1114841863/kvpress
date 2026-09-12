from tools.analyze_kvzap_route_a4210_modeled_backpressure_envelope import simulate
def test_a4210_virtual_reducer_reports_modelled_backpressure_only():
 e=lambda s:{"source_decisions":[{"source":x,"outcome":"partial" if x in s else "skip"} for x in ("hot","pending","packed")]}
 balanced=simulate([e({"hot","packed"}),e({"hot","pending","packed"})],{"hot":1,"pending":1,"packed":1,"reducer":1},1)
 slow=simulate([e({"hot","packed"}),e({"hot","pending","packed"})],{"hot":1,"pending":1,"packed":1,"reducer":2},1)
 assert balanced["modeled_split_state_exports"]==5 and balanced["modeled_fan_in_merge_tasks"]==2 and balanced["modeled_backpressured_merge_tasks"]==0
 assert slow["co_located_cross_engine_exports"]==0 and slow["modeled_backpressured_merge_tasks"]>0
