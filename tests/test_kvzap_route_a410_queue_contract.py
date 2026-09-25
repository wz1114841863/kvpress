from types import SimpleNamespace
from tools.simulate_kvzap_route_a492_record_granular_engine import MicroOp
from tools.simulate_kvzap_route_a410_queue_contract import ORGANIZATIONS, replay

def tx(index, bank): return SimpleNamespace(index=index,arrival_ordinal=0,predecessors=frozenset(),banks=frozenset({bank}),layer=0)
def candidate(): return {"banks":2,"read_ports":1,"write_ports":1,"rmw_lanes":1,"commit_slots":0}

def test_lossless_credit_holds_and_later_drains_without_drop():
    transactions=[tx(i,0) for i in range(40)]
    members={i:(MicroOp(i,("x",(i,)),0,"rmw"),) for i in range(40)}
    org={"name":"tiny","shared_capacity_per_layer":1,"staging_capacity_per_layer":1,"credit_control":True}
    result=replay(transactions,[("x",0)],members,candidate(),org,256)
    assert result["completed"]==40 and result["drained_within_declared_bound"]
    assert result["backpressure_event_count"]>0 and result["held_transaction_high_water"]>0

def test_shared_unbounded_reference_has_no_credit_backpressure():
    transactions=[tx(i,0) for i in range(40)]
    members={i:(MicroOp(i,("x",(i,)),0,"rmw"),) for i in range(40)}
    result=replay(transactions,[("x",0)],members,candidate(),ORGANIZATIONS[0],256)
    assert result["backpressure_event_count"]==0 and result["held_transaction_high_water"]==0
