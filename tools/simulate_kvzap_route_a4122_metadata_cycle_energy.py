#!/usr/bin/env python3
"""A4.12.2 declared metadata service/cycle and CACTI-access-energy replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analyze_kvzap_route_a442_cross_anchor_activation_contract import sha256_file
from tools.analyze_kvzap_route_a461_activation_burst_envelope import read_completed
from tools.analyze_kvzap_route_a480_commit_aware_backlog import dependency_predecessors, iter_contexts, make_scheduled_transactions
from tools.export_kvzap_predictor_trace import get_git_commit, stable_hash
from tools.simulate_kvzap_route_a410_queue_contract import LOCAL_CAPACITY, SHARED_CAPACITY, STAGING_CAPACITY
from tools.simulate_kvzap_route_a491_candidate_metadata_engine import LAYOUT
from tools.simulate_kvzap_route_a492_record_granular_engine import MicroOp, build_micro_ops

SCHEMA = "kvzap-route-a4122-metadata-cycle-energy-1.0"
A4120_SCHEMA = "kvzap-route-a4120-metadata-interface-inventory-1.0"
A4121_SCHEMA = "kvzap-route-a4121-metadata-macro-envelope-1.0"
A410_SCHEMA = "kvzap-route-a410-queue-staging-credit-contract-1.0"
A492_SCHEMA = "kvzap-route-a492-record-granular-engine-1.0"
A4120_SHA256 = "e5a7ad30b45be7acbda7c2b0b788fdfa4ee74553d6fc93bc9317dce0c4be3534"
A4121_SHA256 = "d5f0f436251cb607b884e3102788caf2e775e398542686ad9ca88b58a96e3f7d"
A410_SHA256 = "97f9cec11c8ffff95ce8405d303f35ddf76ea2c4078512f0d98d38e6ec0ec9e4"
A492_SHA256 = "746a03453914294ecd7a48333bebe60d047689626f3ee8e3e4c76def5e00dae8"
BANKS = 8


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="A4.12.2 fixed metadata cycle/service and estimated SRAM-energy replay; declared model only, not hardware timing or RTL.")
    p.add_argument("--a4120-report", type=Path, required=True)
    p.add_argument("--a4121-report", type=Path, required=True)
    p.add_argument("--a410-report", type=Path, required=True)
    p.add_argument("--a492-report", type=Path, required=True)
    p.add_argument("--a468220-trace", type=Path, required=True)
    p.add_argument("--a471-trace", type=Path, required=True)
    p.add_argument("--post-trace-cycle-limit", type=int, default=4096, help="Fixed declared drain bound in service-model cycles, not latency.")
    p.add_argument("--preflight-only", action="store_true", help="Validate frozen bindings and service mappings without output or replay.")
    p.add_argument("--output-dir", type=Path, required=True, help="Previously absent output directory only.")
    return p.parse_args()


def summary(values: list[int]) -> dict[str, int]:
    if not values:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "sum": 0}
    ordered = sorted(values)
    def at(q: float) -> int: return ordered[int((len(ordered) - 1) * q)]
    return {"count": len(ordered), "min": ordered[0], "p50": at(.5), "p95": at(.95), "p99": at(.99), "max": ordered[-1], "sum": sum(ordered)}


def required_report(path: Path, schema: str, expected_sha: str, label: str) -> dict[str, Any]:
    if not path.is_file() or sha256_file(path) != expected_sha:
        raise ValueError(f"{label} requires its accepted exact SHA-256 input")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema_version") != schema or report.get("status") != "complete":
        raise ValueError(f"{label} report is incomplete or schema-incompatible")
    return report


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


def validate(args: argparse.Namespace) -> dict[str, Any]:
    a4120 = required_report(args.a4120_report, A4120_SCHEMA, A4120_SHA256, "A4.12.0")
    a4121 = required_report(args.a4121_report, A4121_SCHEMA, A4121_SHA256, "A4.12.1")
    a410 = required_report(args.a410_report, A410_SCHEMA, A410_SHA256, "A4.10")
    a492 = required_report(args.a492_report, A492_SCHEMA, A492_SHA256, "A4.9.2")
    if a4121.get("input_artifacts", {}).get("a4120_report_sha256") != A4120_SHA256:
        raise ValueError("A4.12.1 is not bound to accepted A4.12.0")
    service = a4120["interface_inventory"]["frozen_service_requirement"]
    logical = a4120["interface_inventory"]["logical_resource_contract"]
    if service.get("bank_count") != BANKS or service.get("mapping") != "head_affine_v1":
        raise ValueError("A4.12.0 HA8-wide service requirement changed")
    if (logical.get("local_queue_capacity_per_bank_transaction_groups"), logical.get("shared_overflow_capacity_per_layer_transaction_groups"), logical.get("staging_capacity_per_layer_transaction_groups")) != (LOCAL_CAPACITY, SHARED_CAPACITY, STAGING_CAPACITY):
        raise ValueError("A4.10 logical queue contract changed")
    guards = a410.get("semantic_guards", {})
    for key in ("a492_record_granular_execution_fixed_without_new_variant", "ha8_wide_primary_and_ha8_base_control_only", "transaction_fifo_ownership_and_single_commit_boundary_unchanged", "lossless_credit_only_delays_transactions_without_drop_or_reorder"):
        if guards.get(key) is not True: raise ValueError("A4.10 semantic guard missing")
    if a410.get("input_artifacts", {}).get("a492_report_sha256") != A492_SHA256:
        raise ValueError("A4.10 is not bound to accepted A4.9.2")
    if a410.get("input_artifacts", {}).get("a468220_trace_sha256") != sha256_file(args.a468220_trace) or a410.get("input_artifacts", {}).get("a471_trace_sha256") != sha256_file(args.a471_trace):
        raise ValueError("A4.10 raw trace binding mismatch")
    a492_guards = a492.get("semantic_guards", {})
    for key in ("record_granular_interleaving_is_internal_and_all_external_publication_is_commit_gated", "same_record_lock_is_explicit_and_released_only_at_group_commit", "no_third_execution_granularity_or_semantic_variant_introduced"):
        if a492_guards.get(key) is not True: raise ValueError("A4.9.2 semantic guard missing")
    wide = next((x for x in a492.get("config", {}).get("candidates", []) if x.get("name") == "ha8_wide"), None)
    if wide != {"name":"ha8_wide", "banks":8, "mapping":"head_affine_v1", "read_ports":2, "write_ports":2, "rmw_lanes":2, "queue_groups_per_bank":32, "commit_slots":0}:
        raise ValueError("A4.9.2 HA8-wide declared candidate changed")
    if args.post_trace_cycle_limit < 0: raise ValueError("negative drain limit")
    return {"a4120": a4120, "a4121": a4121, "macros": macro_metrics(a4121)}


@dataclass(frozen=True)
class Active:
    finish: int
    member: MicroOp
    resources: tuple[tuple[int, str], ...]


def duration(operation: str) -> int:
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


def replay(transactions: list[Any], opportunities: list[tuple[str, int]], members: dict[int, tuple[MicroOp, ...]], candidate: str, macros: dict[str, dict[str, float]], drain_limit: int) -> dict[str, Any]:
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
                active.append(Active(tick + duration(member.operation), member, resources)); busy.update(resources); issued += 1
        for resource, count in busy.items(): occupancy[resource] += count
        for bank in range(BANKS): local_samples[bank].append(local_count[bank])
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
        "queue_residence_service_model_cycles":{"first_micro_op_delay":summary([first_start[i]-transactions[i].arrival_ordinal for i in first_start]),"commit_delay":summary([commit_tick[i]-transactions[i].arrival_ordinal for i in commit_tick]),"member_done_to_commit_wait":summary([commit_tick[i]-member_done_tick[i] for i in commit_tick])},
        "semantic_commit_publication_groups_per_service_cycle":{"committed_groups":sum(committed_per_tick),"average":sum(committed_per_tick)/tick if tick else 0.0,"peak":max(committed_per_tick,default=0),"boundary":"Observed frozen semantic publication rate only; A4.12.2 does not infer a physical commit controller or commit-port throughput."},
        "per_bank_local_occupancy":{str(b):summary(values) for b,values in enumerate(local_samples)}, "trace_end_residual_backlog":len(local)+len(active_groups)+sum(map(len,shared.values()))+sum(map(len,staging.values()))+sum(map(len,held.values()))+len(active),
        "blocking_observation_counts":dict(reasons), "macro_access_and_estimated_sram_dynamic_energy":estimate, "estimated_sram_dynamic_energy_pj_excluding_unestimated_registers":total_pj,
        "boundary":"Service cycles and resource slots are declared A4.12.2 model coordinates, not measured timing, a selected macro port count, throughput, PDK, layout, RTL, or architecture evidence. The sole frozen semantic commit boundary is preserved without inventing a physical global commit controller. CACTI energy is estimated only from counted SRAM accesses and excludes unestimated registers and all controller/payload costs."}


def main() -> None:
    args = parse_args(); checked = validate(args)
    if args.preflight_only:
        print("A4.12.2 preflight passed: A4.12.0/A4.12.1/A4.10/A4.9.2 exact bindings and fixed M1/M2/M3 service mappings validated; no output created."); return
    if args.output_dir.exists(): raise FileExistsError(f"output directory already exists: {args.output_dir}")
    profile = {"layout":LAYOUT,"bank_count":BANKS,"bank_mapping":"head_affine_v1"}
    rows=[]
    for key, records, groups in iter_contexts(args.a468220_trace,args.a471_trace):
        predecessors,_ = dependency_predecessors(records,groups)
        txs,ops = make_scheduled_transactions(groups,predecessors,profile)
        ha8={"name":"ha8_wide","banks":8,"mapping":"head_affine_v1","read_ports":2,"write_ports":2,"rmw_lanes":2,"queue_groups_per_bank":32,"commit_slots":0}
        members=build_micro_ops(groups,txs,ha8)
        for candidate in ("M1_banked_sram_pipelined_rmw","M2_replicated_or_duplicated_control_storage","M3_register_hot_state_with_sram_backing"):
            rows.append({"anchor":key[0],"workload":key[1],"evaluation_horizon_append_opportunities":key[2],"organization_label":key[3],"physical_candidate":candidate,"result":replay(txs,ops,members,candidate,checked["macros"],args.post_trace_cycle_limit)})
    config={"stage":"A4.12.2","fixed_execution":"A4.9.2 record-granular HA8-wide only","queue_contract":"local32/shared256/staging512 only","physical_candidates":["M1_banked_sram_pipelined_rmw","M2_replicated_or_duplicated_control_storage","M3_register_hot_state_with_sram_backing"],"service_cycle":"declared arbitration/access coordinate; not CACTI ns or a clock period","commit_publish":"unchanged A4.9.2 single external boundary with no synthesized global commit slot; all same-coordinate ready groups publish together"}
    report={"schema_version":SCHEMA,"status":"complete","created_at":datetime.now(timezone.utc).isoformat(),"git_commit":get_git_commit(),"execution_classification":"fixed trace-driven declared metadata service/cycle model plus CACTI-access-count estimated SRAM dynamic energy; not hardware timing, throughput measurement, PDK, physical implementation, architecture, or RTL evidence","input_artifacts":{"a4120_report_sha256":A4120_SHA256,"a4121_report_sha256":A4121_SHA256,"a410_report_sha256":A410_SHA256,"a492_report_sha256":A492_SHA256,"a468220_trace_sha256":sha256_file(args.a468220_trace),"a471_trace_sha256":sha256_file(args.a471_trace)},"config":config,"config_hash":stable_hash(config),"candidate_context_rows":rows,"semantic_guards":{"only_m1_m2_m3_from_a4121_compared":True,"ha8_wide_record_granular_and_a410_queue_contract_fixed":True,"single_commit_boundary_fifo_ownership_and_dependency_release_remain_commit_gated":True,"no_global_commit_slot_synthesized_when_a492_ha8_wide_declares_none":True,"no_pruning_admission_queue_or_execution_variant_introduced":True,"cacti_pj_per_access_multiplied_only_by_explicit_macro_access_counts":True,"m3_register_energy_not_invented":True,"no_hardware_measurement_or_rtl_claim":True},"boundaries":["A4.12.2 service cycles are declared model coordinates rather than CACTI ns, a clock period, timing closure, or measured throughput.","The frozen single semantic commit boundary is preserved, but no physical global commit controller or commit-port throughput is inferred when A4.9.2 HA8-wide declares no commit slot.","Estimated SRAM dynamic energy excludes M3 register energy, arbitration, scoreboard, commit, leakage, wiring, clocking, layout, and all KV payload-path energy."]}
    args.output_dir.mkdir(parents=True); output=args.output_dir/"a4122_metadata_cycle_energy_report.json"; output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"A4.12.2 complete: {output} sha256={hashlib.sha256(output.read_bytes()).hexdigest()} rows={len(rows)}")


if __name__ == "__main__": main()
