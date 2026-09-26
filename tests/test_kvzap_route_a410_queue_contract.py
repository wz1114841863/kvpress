from types import SimpleNamespace
from tools.simulate_kvzap_route_a492_record_granular_engine import MicroOp
from tools.simulate_kvzap_route_a410_queue_contract import ORGANIZATIONS, replay

def tx(index, bank, *, arrival=0, predecessors=()): return SimpleNamespace(index=index,arrival_ordinal=arrival,predecessors=frozenset(predecessors),banks=frozenset(bank if isinstance(bank, tuple) else (bank,)),layer=0)
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


def test_started_transaction_remains_schedulable_until_all_members_commit():
    transaction = tx(0, 0)
    members = {0: (
        MicroOp(0, ("first", (0,)), 0, "rmw"),
        MicroOp(0, ("second", (0,)), 0, "rmw"),
    )}
    result = replay([transaction], [("x", 0)], members, candidate(), ORGANIZATIONS[0], 16)
    assert result["completed"] == 1 and result["drained_within_declared_bound"]


def test_older_shared_parent_cannot_be_starved_by_newer_local_children():
    fillers = [tx(i, 0) for i in range(32)]
    parent = tx(32, (0, 1))
    children = [tx(i, 1, arrival=1, predecessors=(parent.index,)) for i in range(33, 65)]
    transactions = fillers + [parent] + children
    members = {item.index: (MicroOp(item.index, ("record", (item.index,)), next(iter(item.banks)), "rmw"),) for item in fillers + children}
    members[parent.index] = (
        MicroOp(parent.index, ("record", (parent.index, 0)), 0, "rmw"),
        MicroOp(parent.index, ("record", (parent.index, 1)), 1, "rmw"),
    )
    result = replay(transactions, [("x", 0), ("x", 0)], members, candidate(), ORGANIZATIONS[0], 256)
    assert result["completed"] == len(transactions)
    assert result["drained_within_declared_bound"]
