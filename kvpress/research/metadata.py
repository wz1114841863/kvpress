"""Declared metadata service, queue, and dynamic-energy replay models.

Coordinates are modeled service opportunities, not physical hardware timing.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any

LAYOUTS = {
    "separated_direct_v1": {
        "storage_object_classes": {
            "frontier_control": ("frontier_control",), "span_descriptor": ("span_descriptor",),
            "ownership_link": ("ownership_link",), "selection_control": ("selection_control",),
        },
    },
    "span_owner_colocated_direct_v1": {
        "storage_object_classes": {
            "frontier_control": ("frontier_control",), "span_owner": ("span_descriptor", "ownership_link"),
            "selection_control": ("selection_control",),
        },
    },
    "control_colocated_direct_v1": {
        "storage_object_classes": {
            "head_control": ("frontier_control", "selection_control"), "span_descriptor": ("span_descriptor",),
            "ownership_link": ("ownership_link",),
        },
    },
    "both_colocated_direct_v1": {
        "storage_object_classes": {
            "head_control": ("frontier_control", "selection_control"), "span_owner": ("span_descriptor", "ownership_link"),
        },
    },
}


def normalized_object_key(layout: str, record_type: str, record_identity: list[Any], *, layer: int, head: int) -> tuple[str, tuple[Any, ...]]:
    classes = LAYOUTS[layout]["storage_object_classes"]
    object_class = next(name for name, members in classes.items() if record_type in members)
    if object_class == "span_owner": return object_class, (int(record_identity[-1]),)
    if object_class == "head_control": return object_class, (layer, head)
    return object_class, tuple(record_identity)


BANK_COUNTS = (1, 4, 8)


def fnv1a_64(text: str) -> int:
    value = 0xCBF29CE484222325
    for byte in text.encode("utf-8"):
        value ^= byte
        value = (value * 0x100000001B3) & ((1 << 64) - 1)
    return value


def bank_index(mapping: str, bank_count: int, object_key: tuple[str, tuple[Any, ...]], *, layer: int, head: int) -> int:
    if bank_count not in BANK_COUNTS:
        raise ValueError("undeclared bank-count sensitivity")
    if mapping == "head_affine_v1":
        encoded = f"{layer}:{head}"
    elif mapping == "object_identity_striped_v1":
        encoded = repr(object_key)
    else:
        raise ValueError(f"unknown bank mapping {mapping}")
    return fnv1a_64(encoded) % bank_count


def lower_transaction(row: dict[str, Any], layout: str) -> dict[tuple[str, tuple[Any, ...]], str]:
    """Explicit semantic-set lowering; never a hardware access count."""
    flags: dict[tuple[str, tuple[Any, ...]], set[str]] = defaultdict(set)
    for set_name, flag in (("read_set", "read"), ("write_set", "write"), ("rmw_set", "rmw"), ("release_set", "release")):
        for item in row[set_name]:
            object_key = normalized_object_key(layout, str(item["record_type"]), list(item["record_identity"]), layer=int(row["layer"]), head=int(row["kv_head"]))
            flags[object_key].add(flag)
    lowered: dict[tuple[str, tuple[Any, ...]], str] = {}
    for object_key, object_flags in flags.items():
        if "rmw" in object_flags or ("read" in object_flags and ("write" in object_flags or "release" in object_flags)):
            lowered[object_key] = "rmw"
        elif "write" in object_flags or "release" in object_flags:
            lowered[object_key] = "write"
        elif object_flags == {"read"}:
            lowered[object_key] = "read"
        else:
            raise AssertionError(f"unlowerable semantic-set flags: {object_flags}")
    if not lowered:
        raise AssertionError("semantic transaction lowered to no modeled storage object")
    return lowered


@dataclass(frozen=True)
class ScheduledTransaction:
    index: int
    phase: str
    checkpoint: int
    layer: int
    head: int
    arrival_ordinal: int
    predecessors: frozenset[int]
    demands: Counter[tuple[int, str]]
    banks: frozenset[int]

LAYOUT = "both_colocated_direct_v1"

CANDIDATES = (
    {"name": "ha4_base", "banks": 4, "mapping": "head_affine_v1", "read_ports": 1, "write_ports": 1, "rmw_lanes": 1, "queue_groups_per_bank": 32, "commit_slots": 0},
    {"name": "ha8_base", "banks": 8, "mapping": "head_affine_v1", "read_ports": 1, "write_ports": 1, "rmw_lanes": 1, "queue_groups_per_bank": 32, "commit_slots": 0},
    {"name": "ha8_wide", "banks": 8, "mapping": "head_affine_v1", "read_ports": 2, "write_ports": 2, "rmw_lanes": 2, "queue_groups_per_bank": 32, "commit_slots": 0},
    {"name": "st8_base", "banks": 8, "mapping": "object_identity_striped_v1", "read_ports": 1, "write_ports": 1, "rmw_lanes": 1, "queue_groups_per_bank": 32, "commit_slots": 1},
)

def candidate_summarize(values: list[int]) -> dict[str, int]:
    if not values: return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    s = sorted(values); n = len(s)
    at = lambda q: s[min(n - 1, max(0, int((n - 1) * q)))]
    return {"count": n, "min": s[0], "p50": at(.50), "p95": at(.95), "p99": at(.99), "max": s[-1], "sum": sum(s)}

def candidate_duration(tx: Any, candidate: dict[str, Any]) -> int:
    """Declared atomic group reservation: ports/lane capacity set modeled cycles."""
    reads = sum(v for (_, op), v in tx.demands.items() if op == "read")
    writes = sum(v for (_, op), v in tx.demands.items() if op == "write")
    rmw = sum(v for (_, op), v in tx.demands.items() if op == "rmw")
    service = max((reads + candidate["read_ports"] - 1) // candidate["read_ports"], (writes + candidate["write_ports"] - 1) // candidate["write_ports"], 2 * ((rmw + candidate["rmw_lanes"] - 1) // candidate["rmw_lanes"]), 1)
    return service + (1 if len(tx.banks) > 1 else 0)

def candidate_replay(transactions: list[Any], opportunities: list[tuple[str, int]], candidate: dict[str, Any], drain_limit: int) -> dict[str, Any]:
    arrivals: dict[int, list[Any]] = defaultdict(list)
    for tx in transactions: arrivals[tx.arrival_ordinal].append(tx)
    pending: list[Any] = []; committed: set[int] = set(); active: list[tuple[int, Any]] = []
    bank_until = [0] * candidate["banks"]; coordinator_until = 0; starts = {}; causes = Counter(); peak = 0; overflow = 0; tick = 0
    last_arrival = len(opportunities) - 1
    while tick <= last_arrival or pending or active:
        if tick > last_arrival + drain_limit: break
        for tx in arrivals.get(tick, []): pending.append(tx)
        finished = [item for item in active if item[0] <= tick]
        active = [item for item in active if item[0] > tick]
        committed.update(tx.index for _, tx in finished)
        peak = max(peak, len(pending) + len(active))
        bank_queued = Counter(b for tx in pending for b in tx.banks)
        overflow = max(overflow, max(bank_queued.values(), default=0) - candidate["queue_groups_per_bank"])
        kept = []
        for tx in pending:
            if any(p not in committed for p in tx.predecessors): causes["intrinsic_dependency"] += 1; kept.append(tx); continue
            if any(bank_until[b] > tick for b in tx.banks): causes["bank_or_rmw_reservation"] += 1; kept.append(tx); continue
            if len(tx.banks) > 1 and candidate["commit_slots"] and coordinator_until > tick: causes["cross_bank_commit"] += 1; kept.append(tx); continue
            d = candidate_duration(tx, candidate); starts[tx.index] = tick
            for b in tx.banks: bank_until[b] = tick + d
            if len(tx.banks) > 1 and candidate["commit_slots"]: coordinator_until = tick + d
            active.append((tick + d, tx))
        pending = kept; tick += 1
    delays = [starts[t.index] - t.arrival_ordinal for t in transactions if t.index in starts]
    return {"completed": len(committed), "total": len(transactions), "drained_within_declared_bound": len(committed) == len(transactions), "abstract_cycles_elapsed": tick, "transaction_start_delay_abstract_cycles": candidate_summarize(delays), "peak_inflight_or_queued_transaction_groups": peak, "queue_overflow_groups_observed": overflow, "blocking_observation_counts": dict(causes), "model_boundary": "One logical opportunity introduces arrivals at one abstract cycle. An atomic group reserves all touched modeled banks until its declared read/write/RMW service completes; this is a conservative candidate service model, not an SRAM atomic, calibrated timing, or hardware latency."}

def record_summarize(values: list[int]) -> dict[str, int]:
    if not values:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    ordered = sorted(values)
    def at(fraction: float) -> int:
        return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]
    return {"count": len(ordered), "min": ordered[0], "p50": at(.50), "p95": at(.95),
            "p99": at(.99), "max": ordered[-1], "sum": sum(ordered)}

@dataclass(frozen=True)
class MicroOp:
    transaction_index: int
    object_key: tuple[str, tuple[Any, ...]]
    bank: int
    operation: str

@dataclass(frozen=True)
class ActiveMicroOp:
    finish_tick: int
    micro_op: MicroOp

def micro_op_duration(operation: str) -> int:
    if operation in {"read", "write"}:
        return 1
    if operation == "rmw":
        return 2
    raise ValueError(f"undeclared modeled operation: {operation}")

def build_micro_ops(groups: list[dict[str, Any]], transactions: list[ScheduledTransaction], candidate: dict[str, Any]) -> dict[int, tuple[MicroOp, ...]]:
    """Lower one immutable group to one member micro-op per modeled object."""
    if len(groups) != len(transactions):
        raise AssertionError("immutable group/transaction cardinality mismatch")
    result: dict[int, tuple[MicroOp, ...]] = {}
    for index, (group, transaction) in enumerate(zip(groups, transactions)):
        if transaction.index != index:
            raise AssertionError("transaction index diverged from immutable group order")
        lowered = lower_transaction(group, LAYOUT)
        members = tuple(sorted((
            MicroOp(
                transaction_index=index,
                object_key=object_key,
                bank=bank_index(str(candidate["mapping"]), int(candidate["banks"]), object_key,
                                layer=int(group["layer"]), head=int(group["kv_head"])),
                operation=operation,
            )
            for object_key, operation in lowered.items()
        ), key=lambda item: repr(item.object_key)))
        if len({member.object_key for member in members}) != len(members):
            raise AssertionError("one transaction contains duplicate modeled-object micro-ops")
        demand = Counter((member.bank, member.operation) for member in members)
        if demand != transaction.demands or frozenset(member.bank for member in members) != transaction.banks:
            raise AssertionError("record micro-op lowering does not exactly reproduce A4.9.1 demand")
        result[index] = members
    return result

def whole_bank_queue_observations(transactions: list[ScheduledTransaction], opportunities: list[tuple[str, int]], candidate: dict[str, Any], drain_limit: int) -> dict[str, Any]:
    """Instrument the unchanged A4.9.1 algorithm without altering its result."""
    arrivals: dict[int, list[ScheduledTransaction]] = defaultdict(list)
    for transaction in transactions:
        arrivals[transaction.arrival_ordinal].append(transaction)
    pending: list[ScheduledTransaction] = []
    committed: set[int] = set()
    active: list[tuple[int, ScheduledTransaction]] = []
    bank_until = [0] * int(candidate["banks"])
    coordinator_until = 0
    peak_by_bank = [0] * int(candidate["banks"])
    tick = 0
    last_arrival = len(opportunities) - 1
    while tick <= last_arrival or pending or active:
        if tick > last_arrival + drain_limit:
            break
        pending.extend(arrivals.get(tick, []))
        finished = [item for item in active if item[0] <= tick]
        active = [item for item in active if item[0] > tick]
        committed.update(transaction.index for _, transaction in finished)
        queued = Counter(bank for transaction in pending for bank in transaction.banks)
        for bank in range(int(candidate["banks"])):
            peak_by_bank[bank] = max(peak_by_bank[bank], queued[bank])
        retained: list[ScheduledTransaction] = []
        for transaction in pending:
            if any(parent not in committed for parent in transaction.predecessors):
                retained.append(transaction); continue
            if any(bank_until[bank] > tick for bank in transaction.banks):
                retained.append(transaction); continue
            if len(transaction.banks) > 1 and candidate["commit_slots"] and coordinator_until > tick:
                retained.append(transaction); continue
            reads = sum(value for (_, operation), value in transaction.demands.items() if operation == "read")
            writes = sum(value for (_, operation), value in transaction.demands.items() if operation == "write")
            rmw = sum(value for (_, operation), value in transaction.demands.items() if operation == "rmw")
            duration = max(
                (reads + candidate["read_ports"] - 1) // candidate["read_ports"],
                (writes + candidate["write_ports"] - 1) // candidate["write_ports"],
                2 * ((rmw + candidate["rmw_lanes"] - 1) // candidate["rmw_lanes"]), 1,
            ) + (1 if len(transaction.banks) > 1 else 0)
            for bank in transaction.banks:
                bank_until[bank] = tick + duration
            if len(transaction.banks) > 1 and candidate["commit_slots"]:
                coordinator_until = tick + duration
            active.append((tick + duration, transaction))
        pending = retained
        tick += 1
    return {
        "peak_queued_transaction_groups_per_bank": record_summarize(peak_by_bank),
        "queue_occupancy_definition": "A4.9.1 pending transaction groups touching each modeled bank immediately before unchanged whole-bank selection; active groups are excluded.",
    }

def record_granular_replay(transactions: list[ScheduledTransaction], opportunities: list[tuple[str, int]], micro_ops: dict[int, tuple[MicroOp, ...]], candidate: dict[str, Any], drain_limit: int) -> dict[str, Any]:
    """Interleave only micro-ops; all semantic publication remains at group commit."""
    arrivals: dict[int, list[int]] = defaultdict(list)
    for transaction in transactions:
        arrivals[transaction.arrival_ordinal].append(transaction.index)
    pending: list[int] = []
    committed: set[int] = set()
    completed_members: dict[int, set[MicroOp]] = defaultdict(set)
    started_members: dict[int, set[MicroOp]] = defaultdict(set)
    locks: dict[tuple[str, tuple[Any, ...]], int] = {}
    active: list[ActiveMicroOp] = []
    transaction_first_start: dict[int, int] = {}
    transaction_commit_tick: dict[int, int] = {}
    reasons: Counter[str] = Counter()
    peak_queue_by_bank = [0] * int(candidate["banks"])
    active_samples: list[int] = []
    coordinator_until = 0
    tick = 0
    last_arrival = len(opportunities) - 1
    while tick <= last_arrival or pending or active:
        if tick > last_arrival + drain_limit:
            break
        pending.extend(arrivals.get(tick, []))
        finished = [item for item in active if item.finish_tick <= tick]
        active = [item for item in active if item.finish_tick > tick]
        for item in finished:
            completed_members[item.micro_op.transaction_index].add(item.micro_op)
        # Commit is the sole visibility/release point.  Stable immutable order is
        # retained even when internal members completed in a different order.
        for index in list(pending):
            transaction = transactions[index]
            if any(parent not in committed for parent in transaction.predecessors):
                continue
            if len(completed_members[index]) != len(micro_ops[index]):
                continue
            cross_bank = len(transaction.banks) > 1
            if cross_bank and candidate["commit_slots"] and coordinator_until > tick:
                reasons["cross_bank_commit_coordination"] += 1
                continue
            if cross_bank and candidate["commit_slots"]:
                coordinator_until = tick + 1
            pending.remove(index)
            committed.add(index)
            transaction_commit_tick[index] = tick
            for member in micro_ops[index]:
                if locks.get(member.object_key) != index:
                    raise AssertionError("transaction committed without owning every member lock")
                del locks[member.object_key]
        # This is the same per-bank *queued transaction group* definition used
        # above for A4.9.1: a group leaves the queue on its first internal start.
        queued = Counter(
            bank for index in pending if not started_members[index]
            for bank in transactions[index].banks
        )
        for bank in range(int(candidate["banks"])):
            peak_queue_by_bank[bank] = max(peak_queue_by_bank[bank], queued[bank])
        active_by_resource = Counter((item.micro_op.bank, item.micro_op.operation) for item in active)
        for index in pending:
            transaction = transactions[index]
            if any(parent not in committed for parent in transaction.predecessors):
                reasons["intrinsic_dependency"] += 1
                continue
            for member in micro_ops[index]:
                if member in started_members[index]:
                    continue
                lock_owner = locks.get(member.object_key)
                if lock_owner is not None and lock_owner != index:
                    reasons["same_record_lock"] += 1
                    continue
                limit_name = {"read": "read_ports", "write": "write_ports", "rmw": "rmw_lanes"}[member.operation]
                if active_by_resource[(member.bank, member.operation)] >= int(candidate[limit_name]):
                    reasons[f"bank_{member.operation}_port" if member.operation != "rmw" else "rmw_lane"] += 1
                    continue
                locks[member.object_key] = index
                started_members[index].add(member)
                transaction_first_start.setdefault(index, tick)
                active.append(ActiveMicroOp(tick + micro_op_duration(member.operation), member))
                active_by_resource[(member.bank, member.operation)] += 1
        active_samples.append(len(active))
        tick += 1
    first_start_delays = [transaction_first_start[index] - transaction.arrival_ordinal for index, transaction in enumerate(transactions) if index in transaction_first_start]
    commit_delays = [transaction_commit_tick[index] - transaction.arrival_ordinal for index, transaction in enumerate(transactions) if index in transaction_commit_tick]
    if any(index in committed and any(parent not in committed or transaction_commit_tick[parent] > transaction_commit_tick[index] for parent in transaction.predecessors) for index, transaction in enumerate(transactions)):
        raise AssertionError("a transaction committed before an intrinsic predecessor commit")
    stale_locks = {object_key: owner for object_key, owner in locks.items() if owner in committed}
    if stale_locks:
        raise AssertionError("committed transaction left a same-record lock behind")
    return {
        "completed": len(committed), "total": len(transactions),
        "drained_within_declared_bound": len(committed) == len(transactions),
        "abstract_cycles_elapsed": tick,
        "transaction_first_micro_op_delay_abstract_cycles": record_summarize(first_start_delays),
        "transaction_commit_delay_abstract_cycles": record_summarize(commit_delays),
        "peak_queued_transaction_groups_per_bank": record_summarize(peak_queue_by_bank),
        "queue_overflow_groups_observed": max(0, max(peak_queue_by_bank, default=0) - int(candidate["queue_groups_per_bank"])),
        "active_micro_op_concurrency": record_summarize(active_samples),
        "blocking_observation_counts": {name: reasons[name] for name in (
            "intrinsic_dependency", "same_record_lock", "bank_read_port", "bank_write_port", "rmw_lane", "cross_bank_commit_coordination",
        )},
        "execution_boundary": "Micro-ops may interleave only inside immutable A4.7.1 transaction groups. Every member remains externally invisible until the sole existing group commit; FIFO/ownership/oldest release and all dependencies are commit-gated. Abstract cycles/resources are declared model coordinates, not hardware timing or implementation evidence.",
    }

LOCAL_CAPACITY = 32

SHARED_CAPACITY = 256

STAGING_CAPACITY = 512

QUEUE_REFERENCE_WORD_BITS = 64

def queue_summary(values: list[int]) -> dict[str, int]:
    if not values: return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    values = sorted(values); n = len(values)
    return {"count": n, "min": values[0], "p50": values[int((n-1)*.5)], "p95": values[int((n-1)*.95)], "p99": values[int((n-1)*.99)], "max": values[-1], "sum": sum(values)}

def queue_replay(transactions: list[Any], opportunities: list[tuple[str, int]], members: dict[int, tuple[Any, ...]], candidate: dict[str, Any], org: dict[str, Any], drain_limit: int) -> dict[str, Any]:
    """Lossless queue hierarchy; state is published only by the fixed commit."""
    arrivals: dict[int, list[int]] = defaultdict(list)
    for tx in transactions: arrivals[tx.arrival_ordinal].append(tx.index)
    committed, started, completed = set(), defaultdict(set), defaultdict(set)
    locks: dict[Any, int] = {}; active: list[tuple[int, Any]] = []
    local: set[int] = set(); active_groups: set[int] = set(); arrived: set[int] = set()
    shared: dict[int, deque[int]] = defaultdict(deque); staging: dict[int, deque[int]] = defaultdict(deque); held: dict[int, deque[int]] = defaultdict(deque)
    shared_members: set[int] = set(); staging_members: set[int] = set(); held_members: set[int] = set()
    local_count: Counter[int] = Counter(); shared_count: Counter[int] = Counter(); staging_count: Counter[int] = Counter(); held_count: Counter[int] = Counter()
    layers = sorted({tx.layer for tx in transactions})
    local_samples: list[list[int]] = [[] for _ in range(candidate["banks"])]
    shared_samples: dict[int, list[int]] = defaultdict(list); staging_samples: dict[int, list[int]] = defaultdict(list)
    active_samples: list[int] = []; held_samples: list[int] = []; bp_flags: list[bool] = []; stranded_samples: list[int] = []
    reasons: Counter[str] = Counter(); bp_events = 0; coordinator_until = 0; tick = 0; last = len(opportunities)-1
    def local_counts() -> Counter[int]: return local_count
    def layer_count(pool: Counter[int], layer: int) -> int: return pool[layer]
    def can_local(i: int) -> bool:
        return all(local_count[b] < LOCAL_CAPACITY for b in transactions[i].banks)
    def put_local(i: int) -> None:
        local.add(i)
        for bank in transactions[i].banks: local_count[bank] += 1
    def remove_local(i: int) -> None:
        if i in local:
            local.remove(i)
            for bank in transactions[i].banks: local_count[bank] -= 1
    def put_queue(queue: dict[int, deque[int]], members_set: set[int], counts: Counter[int], i: int) -> None:
        layer = transactions[i].layer; queue[layer].append(i); members_set.add(i); counts[layer] += 1
    def pop_queue(queue: dict[int, deque[int]], members_set: set[int], counts: Counter[int], layer: int) -> int:
        i = queue[layer].popleft(); members_set.remove(i); counts[layer] -= 1; return i
    def has_deferred_work(layer: int) -> bool:
        return bool(shared[layer] or staging[layer] or held[layer])
    def put_arrival(i: int) -> None:
        nonlocal bp_events
        arrived.add(i); layer = transactions[i].layer
        # A fresh transaction may not bypass an older deferred transaction in
        # this layer.  Otherwise children can occupy a parent's required local
        # bank slots before that parent is granted, violating the fixed
        # oldest-selection/dependency contract and creating artificial stalls.
        if not has_deferred_work(layer) and can_local(i): put_local(i); return
        cap = org["shared_capacity_per_layer"]
        if cap is None or shared_count[layer] < cap: put_queue(shared, shared_members, shared_count, i); return
        if org["staging_capacity_per_layer"] and staging_count[layer] < org["staging_capacity_per_layer"]: put_queue(staging, staging_members, staging_count, i); return
        put_queue(held, held_members, held_count, i); bp_events += 1
    def advance_buffers() -> None:
        # FIFO within each layer; per-layer queues avoid a full-backlog rescan.
        changed = True
        while changed:
            changed = False
            for layer in layers:
                cap = org["shared_capacity_per_layer"]
                while staging[layer] and (cap is None or shared_count[layer] < cap):
                    put_queue(shared, shared_members, shared_count, pop_queue(staging, staging_members, staging_count, layer)); changed = True
                while held[layer] and org["staging_capacity_per_layer"] and staging_count[layer] < org["staging_capacity_per_layer"]:
                    put_queue(staging, staging_members, staging_count, pop_queue(held, held_members, held_count, layer)); changed = True
                while held[layer] and not org["staging_capacity_per_layer"] and (cap is None or shared_count[layer] < cap):
                    put_queue(shared, shared_members, shared_count, pop_queue(held, held_members, held_count, layer)); changed = True
                while shared[layer] and can_local(shared[layer][0]):
                    put_local(pop_queue(shared, shared_members, shared_count, layer)); changed = True
    while tick <= last or local or shared_members or staging_members or held_members or active:
        if tick > last + drain_limit: break
        finished = [item for item in active if item[0] <= tick]; active = [item for item in active if item[0] > tick]
        for _, member in finished: completed[member.transaction_index].add(member)
        # The sole A4.7.1 commit boundary releases locks and all dependent work.
        for i in sorted(active_groups):
            tx = transactions[i]
            if any(parent not in committed for parent in tx.predecessors) or len(completed[i]) != len(members[i]): continue
            if len(tx.banks) > 1 and candidate["commit_slots"] and coordinator_until > tick:
                reasons["cross_bank_commit_coordination"] += 1; continue
            if len(tx.banks) > 1 and candidate["commit_slots"]: coordinator_until = tick + 1
            committed.add(i); active_groups.remove(i); remove_local(i)
            for member in members[i]:
                if locks.get(member.object_key) != i: raise AssertionError("commit without all member locks")
                del locks[member.object_key]
        # Existing delayed work has grant priority over this tick's arrivals.
        advance_buffers()
        for i in arrivals.get(tick, []): put_arrival(i)
        advance_buffers()
        counts = local_counts()
        for b in range(candidate["banks"]): local_samples[b].append(counts[b])
        for layer in layers:
            shared_samples[layer].append(shared_count[layer]); staging_samples[layer].append(staging_count[layer])
        stranded_samples.append(sum(LOCAL_CAPACITY-counts[bank] for bank in range(candidate["banks"])) if (shared_members or staging_members or held_members) else 0)
        active_resource = Counter((m.bank, m.operation) for _, m in active)
        # A first member frees only the local *queue* slot.  The transaction
        # remains internally schedulable through commit, otherwise a later
        # member would be stranded after its first sibling starts.
        for i in sorted(local | active_groups):
            tx = transactions[i]
            if any(parent not in committed for parent in tx.predecessors): reasons["intrinsic_dependency"] += 1; continue
            for member in members[i]:
                if member in started[i]: continue
                owner = locks.get(member.object_key)
                if owner is not None and owner != i: reasons["same_record_lock"] += 1; continue
                field = {"read":"read_ports", "write":"write_ports", "rmw":"rmw_lanes"}[member.operation]
                if active_resource[(member.bank, member.operation)] >= candidate[field]: reasons["bank_" + member.operation if member.operation != "rmw" else "rmw_lane"] += 1; continue
                locks[member.object_key] = i; started[i].add(member); active_groups.add(i); active.append((tick + micro_op_duration(member.operation), member)); active_resource[(member.bank, member.operation)] += 1
                remove_local(i)  # Queue slot is released only on first internal start, matching A4.9.2 queue accounting.
        held_samples.append(len(held_members)); bp_flags.append(bool(held_members)); active_samples.append(len(active)); tick += 1
    if any(owner in committed for owner in locks.values()): raise AssertionError("committed transaction retained a lock")
    if any(i in committed and any(parent not in committed for parent in tx.predecessors) for i, tx in enumerate(transactions)): raise AssertionError("commit released an unmet predecessor")
    longest = run = 0
    for flag in bp_flags: run = run + 1 if flag else 0; longest = max(longest, run)
    peak_local = [max(values, default=0) for values in local_samples]
    shared_peaks = [max(values, default=0) for values in shared_samples.values()]
    staging_peaks = [max(values, default=0) for values in staging_samples.values()]
    peak_shared, peak_staging = sum(shared_peaks), sum(staging_peaks)
    return {"completed":len(committed), "total":len(transactions), "drained_within_declared_bound":len(committed)==len(transactions), "abstract_cycles_elapsed":tick,
        "per_bank_local_occupancy":{str(bank):queue_summary(values) for bank, values in enumerate(local_samples)}, "per_bank_peak_occupancy":queue_summary(peak_local), "cross_bank_peak_skew":max(peak_local,default=0)-min(peak_local,default=0),
        "stranded_local_capacity_observations":sum(stranded_samples),
        "shared_overflow_per_layer_peak":queue_summary(shared_peaks), "shared_overflow_total_peak":peak_shared, "shared_overflow_active_opportunities":sum(any(values) for values in zip(*shared_samples.values())) if shared_samples else 0,
        "staging_per_layer_peak":queue_summary(staging_peaks), "staging_total_peak":peak_staging, "backpressure_event_count":bp_events, "backpressure_active_opportunities":sum(bp_flags), "longest_backpressure_opportunity_run":longest, "held_transaction_high_water":max(held_samples,default=0), "trace_end_residual_backlog":len(local)+len(shared_members)+len(staging_members)+len(held_members)+len(active_groups),
        "active_micro_op_concurrency":queue_summary(active_samples), "blocking_observation_counts":dict(reasons),
        "declared_queue_reference_word_bits":QUEUE_REFERENCE_WORD_BITS, "peak_modeled_queue_staging_bits":QUEUE_REFERENCE_WORD_BITS*(sum(peak_local)+peak_shared+peak_staging),
        "boundary":"Queue/staging references and abstract opportunities are declared model quantities, not FIFO/SRAM macro sizing, timing, traffic, throughput, energy, area, architecture, or RTL evidence."}

BANKS = 8

def service_summary(values: list[int]) -> dict[str, int]:
    if not values:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    ordered = sorted(values)
    def at(q: float) -> int: return ordered[int((len(ordered) - 1) * q)]
    return {"count": len(ordered), "min": ordered[0], "p50": at(.5), "p95": at(.95), "p99": at(.99), "max": ordered[-1], "sum": sum(ordered)}

def macro_metrics(a4121: dict[str, Any]) -> dict[str, dict[str, float]]:
    rows: dict[str, dict[str, float]] = {}
    for candidate in a4121.get("candidate_rows", []):
        for macro in candidate.get("macro_rows", []):
            role = str(macro["role"])
            metric = macro["per_instance_cacti_proxy"]
            prior = rows.setdefault(role, metric)
            if prior != metric:
                raise ValueError(f"A4.12.1 has inconsistent CACTI proxy metrics for {role}")
    required = {"persistent_head_control_and_span_owner", "replicated_head_control", "span_owner_primary", "span_owner_sram_backing"}
    if set(rows) & required != required:
        raise ValueError("A4.12.1 required macro rows are absent")
    return rows

@dataclass(frozen=True)
class Active:
    finish: int
    member: MicroOp
    resources: tuple[tuple[int, str], ...]

def service_duration(operation: str) -> int:
    if operation in {"read", "write"}: return 1
    if operation == "rmw": return 2
    raise ValueError(f"unknown operation {operation}")

def resource_capacities(candidate: str) -> dict[str, int]:
    if candidate == "M1_banked_sram_pipelined_rmw": return {"unified_1rw": 1}
    if candidate == "M2_replicated_or_duplicated_control_storage": return {"head_replica_0": 1, "head_replica_1": 1, "span_owner_1rw": 1}
    if candidate == "M3_register_hot_state_with_sram_backing": return {"head_hot_register": 2, "span_owner_1rw": 1}
    raise ValueError(candidate)

def access_plan(candidate: str, member: MicroOp, busy: Counter[tuple[int, str]]) -> tuple[tuple[tuple[int, str], ...], dict[str, Counter[str]]]:
    """Fixed candidate mappings.  A returned resource tuple must issue atomically."""
    bank, klass, op = member.bank, member.object_key[0], member.operation
    rw = Counter({"read": 1}) if op == "read" else Counter({"write": 1}) if op == "write" else Counter({"read": 1, "write": 1})
    if candidate == "M1_banked_sram_pipelined_rmw":
        return ((bank, "unified_1rw"),), {"persistent_head_control_and_span_owner": rw}
    if candidate == "M2_replicated_or_duplicated_control_storage":
        if klass == "span_owner": return ((bank, "span_owner_1rw"),), {"span_owner_primary": rw}
        if klass != "head_control": raise AssertionError("unexpected frozen metadata class")
        if op == "read":
            left, right = (bank, "head_replica_0"), (bank, "head_replica_1")
            selected = left if busy[left] <= busy[right] else right
            return (selected,), {"replicated_head_control": rw}
        mirrored = Counter(rw); mirrored["write"] *= 2
        return ((bank, "head_replica_0"), (bank, "head_replica_1")), {"replicated_head_control": mirrored}
    if candidate == "M3_register_hot_state_with_sram_backing":
        if klass == "span_owner": return ((bank, "span_owner_1rw"),), {"span_owner_sram_backing": rw}
        if klass == "head_control": return ((bank, "head_hot_register"),), {"head_control_register_hot_state_unestimated": rw}
        raise AssertionError("unexpected frozen metadata class")
    raise ValueError(candidate)

def can_use(resources: tuple[tuple[int, str], ...], busy: Counter[tuple[int, str]], capacities: dict[str, int]) -> bool:
    return all(busy[item] < capacities[item[1]] for item in resources)

def commit_ready_groups(active_groups: set[int], completed: dict[int, set[MicroOp]], members: dict[int, tuple[MicroOp, ...]], transactions: list[Any], committed: set[int]) -> list[int]:
    """Frozen A4.9.2 publication gate; deliberately no physical commit slot."""
    return [index for index in sorted(active_groups) if len(completed[index]) == len(members[index]) and all(parent in committed for parent in transactions[index].predecessors)]

def service_replay(transactions: list[Any], opportunities: list[tuple[str, int]], members: dict[int, tuple[MicroOp, ...]], candidate: str, macros: dict[str, dict[str, float]], drain_limit: int) -> dict[str, Any]:
    capacities = resource_capacities(candidate)
    arrivals: dict[int, list[int]] = defaultdict(list)
    for tx in transactions: arrivals[tx.arrival_ordinal].append(tx.index)
    local, active_groups, committed = set(), set(), set()
    started: dict[int, set[MicroOp]] = defaultdict(set); completed: dict[int, set[MicroOp]] = defaultdict(set)
    locks: dict[Any, int] = {}; active: list[Active] = []
    shared: dict[int, deque[int]] = defaultdict(deque); staging: dict[int, deque[int]] = defaultdict(deque); held: dict[int, deque[int]] = defaultdict(deque)
    local_count: Counter[int] = Counter(); shared_count: Counter[int] = Counter(); staging_count: Counter[int] = Counter(); held_count: Counter[int] = Counter()
    layers = sorted({tx.layer for tx in transactions}); first_start: dict[int, int] = {}; commit_tick: dict[int, int] = {}; member_done_tick: dict[int, int] = {}
    reasons: Counter[str] = Counter(); access_counts: dict[str, Counter[str]] = defaultdict(Counter); committed_per_tick: list[int] = []; issue_per_tick: list[int] = []; occupancy: Counter[tuple[int, str]] = Counter(); local_samples: list[list[int]] = [[] for _ in range(BANKS)]
    # These are declared transaction-group state samples, not physical FIFO
    # measurements.  Keep them alongside the existing local samples so a later
    # workload-aligned replay can report whether the frozen lossless contract
    # actually used its shared/staging/held tiers without changing arbitration.
    shared_peaks: Counter[int] = Counter(); staging_peaks: Counter[int] = Counter(); held_peaks: Counter[int] = Counter(); local_peaks: Counter[int] = Counter()
    def sample_queue_high_water() -> None:
        for bank in range(BANKS): local_peaks[bank] = max(local_peaks[bank], local_count[bank])
        for layer in layers:
            shared_peaks[layer] = max(shared_peaks[layer], shared_count[layer])
            staging_peaks[layer] = max(staging_peaks[layer], staging_count[layer])
            held_peaks[layer] = max(held_peaks[layer], held_count[layer])
    tick = 0; last = len(opportunities) - 1
    def can_local(index: int) -> bool: return all(local_count[b] < LOCAL_CAPACITY for b in transactions[index].banks)
    def put_local(index: int) -> None:
        local.add(index)
        for b in transactions[index].banks: local_count[b] += 1
    def remove_local(index: int) -> None:
        if index in local:
            local.remove(index)
            for b in transactions[index].banks: local_count[b] -= 1
    def deferred(layer: int) -> bool: return bool(shared[layer] or staging[layer] or held[layer])
    def enqueue(queue: dict[int, deque[int]], count: Counter[int], index: int) -> None: queue[transactions[index].layer].append(index); count[transactions[index].layer] += 1
    def dequeue(queue: dict[int, deque[int]], count: Counter[int], layer: int) -> int:
        index = queue[layer].popleft(); count[layer] -= 1; return index
    def arrive(index: int) -> None:
        layer = transactions[index].layer
        if not deferred(layer) and can_local(index): put_local(index)
        elif shared_count[layer] < SHARED_CAPACITY: enqueue(shared, shared_count, index)
        elif staging_count[layer] < STAGING_CAPACITY: enqueue(staging, staging_count, index)
        else: enqueue(held, held_count, index)
    def advance() -> None:
        changed = True
        while changed:
            changed = False
            for layer in layers:
                while staging[layer] and shared_count[layer] < SHARED_CAPACITY: enqueue(shared, shared_count, dequeue(staging, staging_count, layer)); changed = True
                while held[layer] and staging_count[layer] < STAGING_CAPACITY: enqueue(staging, staging_count, dequeue(held, held_count, layer)); changed = True
                while shared[layer] and can_local(shared[layer][0]): put_local(dequeue(shared, shared_count, layer)); changed = True
    while tick <= last or local or active_groups or any(shared.values()) or any(staging.values()) or any(held.values()) or active:
        if tick > last + drain_limit: break
        finished = [item for item in active if item.finish <= tick]; active = [item for item in active if item.finish > tick]
        for item in finished:
            completed[item.member.transaction_index].add(item.member)
            if len(completed[item.member.transaction_index]) == len(members[item.member.transaction_index]): member_done_tick[item.member.transaction_index] = tick
        # The unchanged A4.9.2 HA8-wide candidate has commit_slots=0.  Preserve
        # its single visibility boundary but do not synthesize a global serial
        # controller: all groups ready at this coordinate publish together.
        ready = commit_ready_groups(active_groups, completed, members, transactions, committed)
        committed_now = 0
        for index in ready:
            committed.add(index); active_groups.remove(index); commit_tick[index] = tick
            for member in members[index]:
                if locks.get(member.object_key) != index: raise AssertionError("commit without fixed member lock")
                del locks[member.object_key]
            committed_now += 1
        committed_per_tick.append(committed_now)
        advance()
        for index in arrivals.get(tick, []): arrive(index)
        # Sample immediately after the fixed arrival/credit decision and before
        # work is issued.  This preserves a lossless admission high-watermark
        # even when ``advance`` can immediately promote a queue member.
        sample_queue_high_water()
        advance()
        busy: Counter[tuple[int, str]] = Counter(resource for item in active for resource in item.resources)
        issued = 0
        for index in sorted(local | active_groups):
            tx = transactions[index]
            if any(parent not in committed for parent in tx.predecessors): reasons["intrinsic_dependency"] += 1; continue
            for member in members[index]:
                if member in started[index]: continue
                owner = locks.get(member.object_key)
                if owner is not None and owner != index: reasons["same_record_lock"] += 1; continue
                resources, energy = access_plan(candidate, member, busy)
                if not can_use(resources, busy, capacities):
                    reasons["physical_service_" + resources[0][1]] += 1; continue
                locks[member.object_key] = index; started[index].add(member); first_start.setdefault(index, tick); active_groups.add(index); remove_local(index)
                for role, accesses in energy.items(): access_counts[role].update(accesses)
                active.append(Active(tick + service_duration(member.operation), member, resources)); busy.update(resources); issued += 1
        for resource, count in busy.items(): occupancy[resource] += count
        for bank in range(BANKS): local_samples[bank].append(local_count[bank])
        sample_queue_high_water()
        issue_per_tick.append(issued); tick += 1
    if any(owner in committed for owner in locks.values()): raise AssertionError("committed group retained a lock")
    if any(i in committed and any(parent not in committed or commit_tick[parent] > commit_tick[i] for parent in transactions[i].predecessors) for i in committed): raise AssertionError("dependency released before commit")
    estimate: dict[str, Any] = {}; total_pj = 0.0
    for role, counts in sorted(access_counts.items()):
        if role not in macros:
            estimate[role] = {"access_counts": dict(counts), "estimated_dynamic_energy_pj": None, "status": "not_estimated_without_register_library_or_synthesis"}; continue
        metric = macros[role]; energy = counts["read"] * metric["dynamic_read_energy_pj"] + counts["write"] * metric["dynamic_write_energy_pj"]
        estimate[role] = {"access_counts": dict(counts), "read_energy_pj": metric["dynamic_read_energy_pj"], "write_energy_pj": metric["dynamic_write_energy_pj"], "estimated_dynamic_energy_pj": energy}; total_pj += energy
    slots = BANKS * sum(capacities.values())
    return {"completed":len(committed), "total":len(transactions), "drained_within_declared_bound":len(committed)==len(transactions), "service_model_cycles_elapsed":tick,
        "single_operation_latency_service_model_cycles":{"read":1,"write":1,"rmw":2,"commit_publish":1},
        "sustained_issue_rate_micro_ops_per_service_cycle":{"total_micro_ops":sum(issue_per_tick),"average":sum(issue_per_tick)/tick if tick else 0.0,"peak":max(issue_per_tick,default=0)},
        "bank_service_utilization":{"busy_resource_slot_cycles":sum(occupancy.values()),"available_resource_slot_cycles":slots*tick,"fraction":sum(occupancy.values())/(slots*tick) if tick else 0.0,"per_resource_slot_cycles":{f"bank{b}_{r}":occupancy[(b,r)] for b in range(BANKS) for r in capacities}},
        "queue_residence_service_model_cycles":{"first_micro_op_delay":service_summary([first_start[i]-transactions[i].arrival_ordinal for i in first_start]),"commit_delay":service_summary([commit_tick[i]-transactions[i].arrival_ordinal for i in commit_tick]),"member_done_to_commit_wait":service_summary([commit_tick[i]-member_done_tick[i] for i in commit_tick])},
        "semantic_commit_publication_groups_per_service_cycle":{"committed_groups":sum(committed_per_tick),"average":sum(committed_per_tick)/tick if tick else 0.0,"peak":max(committed_per_tick,default=0),"boundary":"Observed frozen semantic publication rate only; A4.12.2 does not infer a physical commit controller or commit-port throughput."},
        "per_bank_local_occupancy":{str(b):service_summary(values) for b,values in enumerate(local_samples)},
        "declared_queue_high_water_transaction_groups":{"local_per_bank":{str(bank):local_peaks[bank] for bank in range(BANKS)},"shared_per_layer":{str(layer):shared_peaks[layer] for layer in layers},"staging_per_layer":{str(layer):staging_peaks[layer] for layer in layers},"held_per_layer":{str(layer):held_peaks[layer] for layer in layers},"boundary":"Post-arrival/pre-service and post-service maxima in the frozen lossless declared replay; not physical FIFO occupancy or provisioned SRAM depth."},
        "trace_end_residual_backlog":len(local)+len(active_groups)+sum(map(len,shared.values()))+sum(map(len,staging.values()))+sum(map(len,held.values()))+len(active),
        "blocking_observation_counts":dict(reasons), "macro_access_and_estimated_sram_dynamic_energy":estimate, "estimated_sram_dynamic_energy_pj_excluding_unestimated_registers":total_pj,
        "boundary":"Service cycles and resource slots are declared A4.12.2 model coordinates, not measured timing, a selected macro port count, throughput, PDK, layout, RTL, or architecture evidence. The sole frozen semantic commit boundary is preserved without inventing a physical global commit controller. CACTI energy is estimated only from counted SRAM accesses and excludes unestimated registers and all controller/payload costs."}
