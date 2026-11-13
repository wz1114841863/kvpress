# Route-A incremental storage and service cost ledger — P0, 2026-11-06

## Scope and disposition

This is a read-only source, interface and accounting audit at
`4b03c7c193a96cf6dbcaabed2d68553e27c79d3c`. Only this new report, its CSV/JSON
evidence and the two live navigation documents are written. No RTL, test,
constraint, generator, synthesis script, frozen input or historical result is
changed. No SSH, tmux operation, simulator, CACTI, DC or STA is invoked.
RD1+PM1 and WCG1 remote completion is not inspected or inferred.

The audit is complete at source/accounting scope. Physical area, access
energy, clock/timing, peak-occupancy proof and integrated net benefit remain
open. The main findings are:

1. P3 contains **1,179,648 B payload plus 18,432 B local sidecar** in its
   functional array child. Both are outside the current DC cell-area number.
2. Current M2 entry arrays contain **19,040 B nominal data**, not the much
   larger A4 pooled-queue provision. The current production word format is
   128 bits; A4 used 64-bit modeled words. These are different inventories.
3. M2 has an existing **0.52857872 mm² public-CACTI 0.032-um proxy** in
   A4.14.1. It is neither a matched cost for current RTL nor a target-library
   macro result. Its queue/staging dynamic access cost is explicitly omitted.
4. Current M2 permits two non-backpressuring, distinct-address write events
   together, potentially with a head lookup. P3 has three independent logical
   access lanes. Neither is directly priced by simply selecting a 1RW RAM.
5. The proxy replaces each **whole child implementation body**, including
   child response/acknowledgement registers and access logic. Parent adapters
   remain mapped. The missing cost is therefore more than bare memory bits.

Machine-readable rows are in
[`route_a_incremental_storage_cost_ledger_p0_20261106.csv`](route_a_incremental_storage_cost_ledger_p0_20261106.csv).
The capacity and cost interpretation is summarized in the
[storage and complete-cost report](../hardware_reports/03_storage_measurement_boundary_and_complete_cost.md).

## Evidence boundaries

The DC reference is the accepted **RD1** run
`dc_feasibility_fair_rd1_shared_20261105_r1`, not either ongoing successor.
Its local [result record](dc_rd1_full_paired_dc_result_20261106.md) reports
Full-KV 23,091.432498 and Route-A 3,388,597.345862 native cell-area units under
the same 2-ns fair-v1 constraints. Wrapper 2,387,543.1337, M2 production owner
175,735.2263 and metadata bridge 85,833.3851 are included hierarchy totals;
they are not additional amounts to add to the top. Parent hierarchy totals
do not price the black-box children. No new remote hash/native-report audit
is claimed in this batch.

The exact M2 word/array section, M2 production-owner section and P3
access/array section are byte-identical between current source and accepted
RD1 source commit `e5d3107`. The synthesis parameter profile and metadata
bridge are also byte-identical. This ties the examined dimensions and
interfaces to RD1 without touching remote input. WCG1's default-off wrapper
branch is not promoted into the accepted mapped result.

The local accepted A4.14.1 report rehashes to
`0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb`.
All four materialized direct-input hashes match. Its A4.14.0 input contains
the fixed M2 proxy figure. A4.12.0/.1/.2 transitive reports named by that
input are absent at the recorded local materialized paths: this audit does
not claim to rehash their native CACTI outputs or rerun their characterization.
The old macro dimensions below are an explicitly labeled reconstruction of
the checked-in builder's formulas, not recovered raw CACTI output.

## Incremental cost inventory

DC inclusion below means inclusion in the retained logic boundary, subject
to normal synthesis optimization. Declared source bits are not a mapped-cell
count. All missing implementation costs remain nonzero/unestimated.

| Item | Capacity / extent | Current DC coverage | Prior A4 coverage / remaining gap |
|---|---|---|---|
| P3 payload stage | 36 × 512 × 512 bits = 1,179,648 B = 1.125 MiB | Excluded child | Capacity and declared movement; no stage macro area or stage dynamic energy |
| P3 local sidecar | 36 × 64 × 64 bits = 18,432 B | Excluded in the same P3 child | Position capacity/traffic do not price local storage/access |
| P3 child protocol | 558 declared response/ack holding bits plus indexing/read/write logic | Excluded with entire child body | No matched implementation cost |
| P3 parent / compact tables / journal | Two tables: 366,336 data bits; other state additional | Included in wrapper hierarchy | Do not add these registers or parent control again as a new macro cost |
| M2 mirrored heads | 2 × 288 × 128 bits = 9,216 B | Excluded child | A4 proxy used different modeled counts/64-bit words; needs reconciliation |
| M2 spans | 614 × 128 bits = 9,824 B | Excluded in same child | Same mismatch; actual access/physical placement unpriced |
| M2 child protocol | 178 declared response/ack holding bits plus access logic | Excluded with entire child body | Two-write/lookup implementation cost missing |
| M2 parent private/reuse state | 36 prepared-group records; 614-slot occupancy/generation/provenance index; control mirrors | Included in M2 owner hierarchy | Already mapped control; exact dynamic energy/physical implementation open |
| Metadata bridge / logical credit | 36 group entries, 8 local counters, 36 shared and staging counters each, 288 stream sequence/tail records | Included in bridge hierarchy | No implemented 36,864-entry queue follows from these counters; old queue mapping unresolved |
| R5 availability/generation | 146,880 × (1 + 8) bits = 165,240 B nominal | Excluded child; parent selection/reclaim retained | Bitmap-only 18,360 B omits generation storage; no matched macro price |
| R5 active/control state | Spec: 288 × 96-bit active descriptors; current PageManager has concrete parent state | Parent logic retained; not a separate free future macro | Reconcile fields before charging anything again |
| S2 payload | Two × 32,768 B on each side | Both payload children excluded; parent controls retained | A4 common proxy 0.580656 mm²; current shell equivalence still non-cancellable |
| Route-A S2 sidecar | Two × 64 × 8 B = 1,024 B | Excluded Route-A child; parent sidecar control retained | Incremental storage/access implementation missing |
| R5 descriptor region/service | 146,880 × 16 B = 2,350,080 B external metadata region | External service excluded; local maintenance/control retained | Capacity is known; physical service/controller/maintenance cost not complete |
| P3 pending backing | Authoritative pending K/V backing; workload/lifecycle dependent | External backing excluded; local transport retained | Declared P3 traffic partly accounted; no additional controller assumed per service |
| R4 / outer partial services | Numeric merge, partial storage and differential provider activity | Structural merge control included; numeric services outside | Arithmetic, RF/SRAM/spill and incremental interconnect cost missing |
| Core memory infrastructure | Controller/PHY/CDC, mapping and service implementation | External; local R1/R2/registry/router retained | Same declared service basis required; common implementation not proven free |

No sum is taken across this table: it mixes DC hierarchy totals, logical
capacity, prior analytical proxies and external service responsibilities.
The two compact tables are **already mapped**; they are not the excluded
M2 head/span entry arrays. P3 local sidecar, S2 sidecar and external packed
position backing are distinct lifecycle provisions, not three names for a
single already-priced memory.

## P3 staging: capacity, lifetime and access concurrency

Source: `RouteAIncrementalSkeletons.scala:2319–2420, 2527–2551,
2866–2966, 3013–3099, 3288–3297`; contracts:
[`architecture_spec.md`](architecture_spec.md) §7 and
[`mr2_p3_array_boundary_contract.md`](mr2_p3_array_boundary_contract.md).

The payload shape is 18,432 words × 512 bits, logically 36 layers × 512
64-B fragments. Eight fragments form one 512-B K+V record; 64 records form
one 32-KiB stage. The separate sidecar is 2,304 words × 64 bits. Neither is
authoritative residency: pending backing remains authoritative until packed
publication. Stage completion waits for matching payload/sidecar write acks;
payload durability, metadata publication and release remain parent decisions.
A read finishing or a write request firing alone does not release the stage.

| Consumer/event | Fields/index | Logical access | Concurrent access allowed by current boundary |
|---|---|---|---|
| Accepted pending fragment | `{layer, fragment, data[511:0]}` | One payload write, tagged ack | Independent of sidecar write and payload read lanes |
| Accepted position binding | `{layer, ordinal, position[63:0]}` | One sidecar write, tagged ack | Can coincide with payload write, including final completion on one layer |
| Packed-write state machine | `{layer, fragment}` → tagged 512-bit data | One payload read with held response | Can overlap filling another layer; parent prevents ordinary fill and packed-read phases on the same layer |

Each lane has one pending ack/response, `ready := !pendingValid`, without
consume-and-replace bypass. Under continuously ready acknowledgement/response
consumers, the child accepts at most one request per two clocks **per lane**.
This is source behavior, not calibrated bandwidth or a new throughput result.
The parent has one packed-write FSM and one global pending payload write and
sidecar write each. Thirty-six stage slots do not imply 36 simultaneous read
ports or 36 independent write ports. Conversely, a single packed writer
does not prove that one stage slot is enough when other layers can remain
reserved/filling/durable or wait for publication.

The child permits all three requests together when their independent pending
bits are clear. The parent separates same-layer payload fill/read phases;
the child itself does not define a general same-address `Mem` read/write
collision value. A physical replacement must preserve legal-parent behavior
and held responses, with collision assumptions explicitly justified. A
single 1RW payload RAM cannot simply accept the observed simultaneous
cross-layer read and write without a banking/port/scheduling proof. No such
physical mapping is selected here.

The sidecar child currently has a write/ack lane and **no sidecar read port**.
Materialized sidecar output is sourced from R3 membership facts; external
position-service responsibilities remain separate. This is an access-map
observation worth tracing before later realization, not authorization to
delete the sidecar or a proof that its lifecycle obligation is unnecessary.

The generic wrapper has 36 stage/observation banks. The current composed
production ingress accepts only one ≤64-member group per reset and reaches
absorbing `StateDone`. That bounded test contour is not evidence of safe
capacity reduction or of steady-state, multi-layer workload throughput.
No maximum simultaneous-layer occupancy proof is supplied by the historical
traces or this audit. The frozen one-page-per-layer envelope is unchanged.

## M2 storage: actual entry arrays versus the A4 proxy

Source: `RouteAIncrementalSkeletons.scala:1761–1910, 1931–2014,
2053–2109, 2196–2285`; profile: `RouteASynthesisControlProjectionProfile.scala`;
contracts: [`mr2_m2_array_boundary_contract.md`](mr2_m2_array_boundary_contract.md)
and [algorithm cost review](../algorithm_reports/06_pre_rtl_cost_ledger_and_architecture_entry.md).

Current production arrays have 288 `(layer, head)` keys, two identical head
replicas, and 614 span slots. Their 128-bit formats are **not** the old
fixture-only `RouteAM2EntryStorage` runtime format. The current head word has
42 non-reserved bits and 86 reserved bits. With synthesis-profile stage/tag
widths of 8 bits, the span has 59 non-reserved bits and 69 reserved bits.
Thus 152,320 nominal array bits include 91,902 reserved bits; the declared
non-reserved fields total 60,418 bits. Production prepares zero reserved
fields and releases zero words. These counts are layout evidence, not a
proof of a safely smaller macro, cell area, or savings: the arrays are
already excluded from the reported DC area, and physical word padding,
reset/valid handling, ports and peripherals remain unchosen.

| Access | Current interface and behavior | Concurrency / physical obligation |
|---|---|---|
| Private-prepare head lookup | One `Decoupled` index; registered full head response, held under backpressure | One outstanding; no response-cycle replace bypass; read samples pre-edge register state |
| Published resolution | `Valid` commit writes both head replicas and one span atomically | No request-ready/backpressure input; can occur in consecutive clocks |
| Exact all-member handoff | Independent `Valid` release clears both heads and one span | No request-ready; can coincide with commit at different head **and** span addresses |
| Lookup + commit/release | Independent lookup-ready and write-valid paths | No child mutual-exclusion guard; aliasing head lookup observes old register value |

Distinct addresses do not imply distinct head-affine banks. The child
asserts head/span non-alias for the two writes, not a different-bank rule.
Both head replicas receive both writes; simply duplicating a 1RW head macro
does not solve a two-write collision. Span allocation uses a global
614-slot priority allocator; a physical eight-bank span mapping is not
selected. Any narrower-port implementation needs a concrete conflict and
atomicity solution; it cannot silently add ready-low to the two `Valid`
event inputs or delay an already accepted publication/handoff decision.

The parent has one pending head lookup and one member response. R3 issues
the two semantic members in order; the abstract A4 `2 read / 2 write / 2 RMW`
service opportunity is **not** the current wrapper's cycle-level port count.
The 614-slot allocation bound and 36 private prepared-group records are
allocated capacities, not evidence that all 614 slots are simultaneously
needed in the composed one-group ingress. Reducing either requires a
separate reachability/capacity proof; none is claimed here.

### What the historical M2 price covers

A4.14.1 and its hash-verified A4.14.0 input retain **0.52857872 mm²**, once
per metadata engine, for the public-CACTI 0.032-um M2 candidate. The checked-in
A4.12.1 builder fixes 64-bit modeled words, 225 modeled head objects, 614
modeled spans, eight banks and 1RW macros. Its formulas reconstruct:

| Historical macro role | Instances / provision |
|---|---|
| Head replicas | 16 × 1,024 B, including small-array padding |
| Span stores | 8 × 1,024 B, including padding |
| Pooled queue/staging shards | 8 × 36,864 B = 294,912 B |
| Total modeled SRAM provision | 32 macro instances, 319,488 B = 312 KiB |

The queue formula is `36 × (8×32 + 256 + 512) × 8 B`. This is the old
builder's **conservative provisioning assumption**, not a new requirement
to instantiate 36,864 physical queue records or proof of simultaneous occupancy.
The current metadata bridge implements logical credit counters and one group
record per layer; it does not instantiate this pooled SRAM. The A4 private/
shared FIFO replay is not automatically a missing production subsystem.
Reconcile the required retained facts and lifetimes to actual runtime owners
before adding any pool; do not price counters as if they held payload records.

A4.14.0's dynamic estimate covers head/span control-entry accesses only.
Queue/staging SRAM accesses, replica/control peripheral activity, clock,
wires, leakage and physical implementation are not fully accounted. The
historical 1RW scheduling model does not establish current Valid-lane
concurrency, 128-bit words, reset, collision semantics or 2-ns macro closure.
Therefore the old proxy is useful prior evidence, **not matched current M2
cost**, and must not be added to DC cell area without reconciliation of
technology, units, overlap and access mapping. No component area split can
be revalidated without the absent A4.12.1 macro/raw reports.

## Required next evidence, in priority order

1. **P3 mapping feasibility:** reconcile the full 36-slot payload/sidecar
   envelope to actual permitted read/write overlap, response holding, reset,
   lifetime and access counts. Establish an implementation candidate and
   charge its child adapters/peripherals as well as storage. No capacity,
   latency or concurrency change is approved by this audit.
2. **M2 interface-to-storage mapping:** resolve lookup plus two Valid write
   lanes, same-bank conflicts, old-data reads, atomic mirror/span updates
   and initialization before pricing any physical memory organization.
3. **M2 provision reconciliation:** map current head/span formats, compact
   membership/journal and credit/group records to retained semantic facts;
   identify whether any additional queue data is actually required. Keep the
   prior 312-KiB analytical provision and current 19,040-B nominal entries as
   separate inventories, not additive obligations or equivalent designs.
4. **Complete the wider ledger:** price excluded R5/S2 storage and numeric/
   external-service increments on the same accounting basis, separating
   proven common provision and differential activity. Do not charge a whole
   controller per logical service, cancel S2 by name, or count retained
   parent logic twice.

These are evidence gaps, not new architecture choices or an authorization for
RTL/macro experiments. Existing compact optimization remains relevant, but
its savings cannot settle these missing costs. A4.14.1's positive differential
dynamic-energy budget is a conditional proxy-ledger constraint, not an area
allowance or proof of hardware net benefit.

## Checks and limitations

- Recomputed the accepted A4.14.1 report hash and all four direct-input hashes.
- Compared the three source sections, complete synthesis profile and bridge
  against accepted RD1 source `e5d3107`; all five comparisons match.
- Reconciled nominal capacities, field widths, omitted child registers,
  logical lane types, same-address rules, entire-child proxy scope and old
  macro formulas. Static checks are recorded in the evidence JSON.
- Existing local M2/P3 boundary guards pass **4/4** with pytest cache disabled.
  These are structural/source guards, not new functional or formal tests.
- Documentation links, JSON/CSV consistency, protected-source hashes and
  `git diff --check` are checked before the documentation-only commit.

No remote state is observed; no new area, timing, power, macro, PPA, system
acceleration or net-hardware-benefit conclusion is made.
