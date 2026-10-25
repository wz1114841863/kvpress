# Dual-DUT measurement-cut freeze — 2026-10-25

**Freeze anchor:** `fc06fdbc763325e55638f6cc164cf251b424a2f2`
**Status:** `functional_measurement_cut_frozen`
**Machine inventory:**
[`measurement_dut_cut_freeze_20261025.json`](measurement_dut_cut_freeze_20261025.json)

## Decision and scope

This record freezes the actual bounded Chisel measurement contours, not the
earlier planning names alone:

- `kvpress.routea.top.FullKVMeasurementDut`; and
- `kvpress.routea.top.RouteAMeasurementDut`.

The machine inventory fixes the exact source-file hashes, instantiated-module
lists, outer interfaces, and comparison classifications used by this decision.
The current source tree contains an unrelated unstaged `.gitignore` edit; it
is outside this inventory and does not alter any listed Chisel file.

This is a **functional measurement-cut freeze**. It does not rename either
DUT as a future synthesis top. It does not select a macro/wrapper/controller/numeric implementation,
authorize DC/CACTI/PPA, or produce an area, energy, timing, throughput, or net-benefit result.

## Actual DUT source contours

### Full-KV

`FullKVMeasurementDut` has the baseline-local chain:

```text
full_kv_read_work_in
  -> FullKVReadProducer -> FullKVDeliveryContextBridge
  -> RouteACoreSideArbiter -> RouteACoreMemIfV1
  -> RouteADeliveryContextRegistry -> RouteATypedDeliveryRouter
  -> FullKVS2ReadEndpoint -> FullKVS2GqaSourceWrapper
  -> full_kv_consumer_commit_in -> FullKVTerminalRetireAdapter
  -> attention_terminal_rsp / runtime_retire_req / session_retire_ack
```

Its active instances are the baseline producer, delivery bridge, endpoint,
S2 completion wrapper, terminal/retire adapter and status collector, plus the
shared `RouteACoreSideArbiter`, `RouteACoreMemIfV1`,
`RouteADeliveryContextRegistry`, and `RouteATypedDeliveryRouter`.
The complete ordered list is in the JSON inventory.

The old Full-KV elaboration defect is explicitly closed in this source freeze:
the shared arbiter's Route-A-only direct-candidate-cancel ingress is driven
inactive and its impossible acknowledgement is consumed. This does not add a
direct-pending owner to Full-KV. `FullKVMeasurementDutSpec` remains the
functional evidence for this path.

### Route-A

`RouteAMeasurementDut` keeps the production-shaped Route-A owner contour:

```text
accepted admission / R3-M2-P3 / R5 publication
  -> R6 accepted authority -> packed activation and R2/R1 transport
  -> S2 READY / source service -> four commits / R4 structural boundary
  -> R6 terminal -> R5/R6 reclaim and retire
```

It also contains the hot path and the approved direct-pending association,
lease/cancel/abort contour. The JSON inventory records every direct instance;
the Route-A list is deliberately not reduced to broad module labels, so a
later top/wrapper review can compare actual ownership rather than infer it
from the architecture diagram.

## Frozen outer interfaces

| DUT | Outer interfaces retained by the current cut | Freeze treatment |
| --- | --- | --- |
| Full-KV | `full_kv_read_work_in`, `external_core_mem_if_v1`, `source_ready_out`, `full_kv_consumer_commit_in`, `attention_terminal_rsp`, `runtime_retire_req`, `session_retire_ack` | `full_kv_read_work_in` and consumer commits are named baseline-local functional contracts. `core_mem_if_v1` is an explicit external memory service. Neither an attention PE nor controller is included. |
| Route-A | frontend lifecycle/retire/terminal/ack; source-plan declaration; pending descriptor registration; hot payload/sidecar and pending payload binding; three functional partial offer and three fragment inputs; functional R4 packet/merge/result/fault; direct-pending fragment output; `external_core_mem_if_v1` | These are the already-declared functional environments and source-service/R4 boundaries. Internal packed demand, publication authorization, descriptor grant and S2 lease are not outer authorization ports. |

The inventory distinguishes an **outer functional boundary** from a test-only
fixture. A functional boundary is not a controller, SRAM/HBM macro, attention
PE, R4 numeric pipeline, or cost-free component.

## Fairness and cost classification at the frozen cut

The 30-record BOM and MBR.1 matrix remain the authoritative accounting map.
This freeze records what the *actual instances* can and cannot establish:

| Classification | Actual observation | Required accounting treatment |
| --- | --- | --- |
| Structurally shared common control | Both DUTs instantiate `RouteACoreSideArbiter`, `RouteACoreMemIfV1`, `RouteADeliveryContextRegistry`, and `RouteATypedDeliveryRouter`, and expose `core_mem_if_v1`. | A later comparison may pair only equal selected configuration/interface behavior; no current cost cancellation follows automatically. |
| Semantically paired, structurally non-identical | Both contours implement matching read-to-S2 READY, four-consumer completion, stale/fault/reset and terminal/retire responsibilities; Full-KV uses baseline-local S2/terminal/status classes while Route-A uses Route-A lifecycle/S2/source-service classes. | Treat as `paired_common_pending_equivalence`, not as equal RTL or a cancellable netlist. A future wrapper/top must prove the required equivalence. |
| Planned common provision absent from current Full-KV source list | `RouteAHotSourcePath` is active only in Route-A; Full-KV has no same-class hot instance. | Do not silently cancel hot control. It remains a measurement-cut difference requiring explicit future Full-KV basis or a differential/common allocation decision. |
| Route-A incremental control/storage | R3/M2/P3, R5, packed activation/ingress/sidecar, direct-pending, R4 structural merge, Route-A status and associated array boundaries appear only in the Route-A DUT. | Remain Route-A incremental and `unestimated_not_zero` where the BOM/SRP plan has no measured evidence. |
| External/reference scope | Memory service, R5 descriptor service, P3 backing, outer partial provider, R4 numeric result/fault, and test-only observers/fixtures are outside the costed DUT. | Keep a named external or excluded row; do not count it as zero or import it as synthesized logic. |

Consequently, the freeze preserves the approved Full-KV fairness contract but
does **not** declare the present Chisel classes a fully equivalent common
hardware implementation. This is an intentional eligibility finding, not a
failure of either functional path.

## Direct-pending limit

The only frozen direct-pending evidence is the approved MR-1B **single-record**
contour: `valid_count = 1`. It covers exact descriptor/source association,
accepted-read lease, pending-to-packed withdrawal before issue, cancel/abort,
R6-owned fault terminal, and legal post-issue lease completion. It must not be
used to claim multi-record association, multi-record endpoint behavior,
physical direct storage, or a general direct-pending cost result. Any
multi-record extension requires a separate association/lifetime/terminal/test
review.

## Reset/init and regression basis

Both DUTs retain explicit `core_mem_if_v1.init_ack` and stale-response reset
behavior. The freeze relies on the current functional evidence:

- Full-KV directed: `FullKVMeasurementDutSpec` (`5/5`) covering success,
  stale/duplicate rejection, response fault, reset/re-init and drain/retire.
- Route-A production contour: `RouteAMeasurementDutR3Spec` (`4/4`) covering
  packed, hot, stale packed response and pre-issue direct withdrawal/fault.
- Latest selected cross-stage regression: `10` suites / `40` tests, completed
  as `13/13` plus `27/27` in the two R5-final logs listed in
  `mr2_r5_availability_array_boundary_contract.md`.
- MR-2 P3/S2/M2/R5 boundary records and
  [`mr2_completion_review.md`](mr2_completion_review.md).

These are functional Chisel/Verilator checks. They do not validate an external
memory implementation, numeric calculation, physical array behavior, or
performance.

## Freeze result and next gate

The dual-DUT measurement cut is now fixed for future realization preparation:
any edit to an inventory-hashed Chisel source invalidates this record and must
be reconciled through a new, dated freeze or a documented successor. The next
allowed task is a **separate realization-preparation review** of future
synthesis-top candidates and array-only wrapper interfaces. It must begin from
this source/port/ownership inventory and may not use it to skip the unresolved
common-equivalence, physical-wrapper, external-service, R4 numeric, or
integration-shell evidence.
