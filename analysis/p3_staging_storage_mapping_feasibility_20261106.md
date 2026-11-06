# P3 staging storage-mapping feasibility — 2026-11-06

## Disposition and fixed boundary

**Protocol-level feasibility is supported; RTL and physical realization are
not closed.** This assessment at `3c5d4ed6b8610b92f486270488a0b9957ba81cca`
does not modify RTL, tests, constraints, frozen inputs or prior results. It
adds this report, a finite-state assessment tool and receipts, and live
navigation. No remote access, HDL simulator, DC, STA or CACTI run occurs.
RD1+PM1 and WCG1 status/input remain untouched and unrefreshed.

The fixed capacity is **36 × 512 × 512-bit payload words = 1,179,648 B**,
plus **36 × 64 × 64-bit local sidecar words = 18,432 B**. Logical capacity,
all word bits, three independent channels, accepted-event ordering, response
latency/holding, ordinary synchronous reset and the unchanged 2-ns fair-v1
constraint must be preserved. No extra clock, serialization visible at the
interface, reduced stage count, sidecar deletion or Full-KV change is allowed.

The most useful next isolated candidate is **one logical 1RW payload service
plus one deferred-write slot and a held read-response adapter**. The current
no-replace handshake creates a guaranteed drain edge after simultaneous
read/write acceptance. This is a storage-local implementation hypothesis,
not a new R2 scheduler, admission policy, publication point or authority.
An independent 1R1W payload service is the simpler functional reference for
future pricing; neither organization is a selected vendor macro.

The [incremental ledger](route_a_incremental_storage_cost_ledger_p0_20261106.md)
remains the cost-boundary authority. This work does not reduce the accepted
RD1 control-only area: P3's child is already excluded from that figure.
It investigates how to implement and price the missing provision reasonably.

## Exact logical ports and edge behavior

Source: `RouteAIncrementalSkeletons.scala:2319–2420, 2866–2966,
2992–3013, 3016–3117`; normative boundaries:
[`mr2_p3_array_boundary_contract.md`](mr2_p3_array_boundary_contract.md),
[`architecture_spec.md`](architecture_spec.md) §7 and
[`dc_feasibility_fair_v1_constraint_freeze_20261029.md`](dc_feasibility_fair_v1_constraint_freeze_20261029.md).

| Lane | Address/data | Accepted operation and response | Independence |
|---|---|---|---|
| Payload write | layer[5:0], fragment[8:0], data[511:0] | Store bytes on accepted edge; tagged ack valid after that edge | Independent of payload read and sidecar write |
| Payload read | layer[5:0], fragment[8:0] | Capture selected word; tagged response valid after accepted edge | Can overlap writes to another layer; child has no same-bank exclusion |
| Sidecar write | layer[5:0], ordinal[6:0], data[63:0] | Store full word and produce tagged ack | Can coincide with both payload lanes |

Each lane uses `request.ready = !pendingValid`. Response consumption clears
the pending flag; it does **not** simultaneously reopen request acceptance
on that same edge. Response tags/data hold while valid and not ready.
No request-ready expression may gain a bank-conflict term or depend on an
unrelated lane's backpressure. No response may gain an extra clock of latency.
Data/tag bits when valid is low are not assigned a new external guarantee.

At the parent, a payload fill is accepted only for Reserved/Filling stages.
Packed reads occur in the serialized packed-write FSM after completion; the
direct test issue/terminal ports assert that the FSM is idle. This supports
separate fill/read phases for one layer, but cross-layer read/write remains
legal. The primary candidate below does not need a new parent phase or
different-layer assumption: it handles simultaneous payload accesses locally.

The reference `Mem` words are **not reset**. Reset clears protocol-valid
state; it does not erase bytes. Requests accepted on a reset edge can still
write the reference Mem even though their response-valid registers reset.
A replacement must preserve this behavior for direct child equivalence, or
prove a narrower parent qualification separately. No such qualification is
assumed by the finite model.

The sidecar has no read port in this child. Its full 64-bit words and write
lane are retained. Addressing is `layer * 64 + ordinal`, not unconditional
concatenation with ordinal[5:0]. The parent restricts ordinal to 0..63, while
the standalone child does not add that assertion; truncating its 7-bit input
would alter out-of-parent alias behavior. Retain the original index arithmetic
or explicitly prove the replacement's legal-domain assumptions.

## Conflict matrix and mapping alternatives

| Accepted events | Storage requirement | Handling without a handshake change |
|---|---|---|
| Payload read only | One payload read | Service directly |
| Payload write only | One payload write | Service directly |
| Read + write, different addresses | Two logical accesses on one edge | 1R1W service, distinct suitable banks, or the buffered 1RW transformation below |
| Same layer, different fragment read + write | Standalone child does not forbid it | Buffered 1RW handles it; per-layer unbuffered 1RW needs a proven parent restriction |
| Same-address read + write | Source Mem does not define a general collision value | Do not invent a new guaranteed value; close emitted-RTL/macro collision correspondence or prove exclusion |
| Any payload event + sidecar write | Independent data stores and ack slots | Separate sidecar write resource; never arbitrate it against payload |
| Read response stalled + later writes | Old read response remains stable | Hold returned data independently of subsequent macro write-output changes |

| Organization | Assessment | Unresolved cost/semantics |
|---|---|---|
| Shared logical 1R1W payload + independent sidecar | Structurally straightforward for concurrent payload accesses | Real macro shape, collision mode, one-edge read availability, held output, padding and price |
| **Logical 1RW payload + one buffered write** | Finite-model positive; recommended next isolated equivalence candidate | Exact adapter RTL, reset-safe drain, macro output hold, timing and complete cost |
| 36 per-layer 512×512-bit 1RW payload banks | Conditional option for the existing parent phase separation | Not an unconditional standalone-child substitute; 36 banks, wide output mux and phase invariant all require accounting/proof |
| One unbuffered shared 1RW payload with priority/stall | Does not preserve the current interface | Either drops an accepted access or changes request-ready/response latency |
| Fewer coarse banks without buffering/conflict solution | Not established by layer separation | Different layers may map to the same physical bank |
| Merge payload and sidecar into one unbuffered port | Does not preserve independent writes | Two accepted write events may coincide, including on one layer |

Physical depth/width tiling is still open. Logical payload depth is 18,432,
not 32,768; a vendor shape rounded to 32,768×512 would provision 2 MiB rather
than 1.125 MiB, and that padding must be charged. Layer banking or depth/width
tiling can preserve useful capacity but adds real decode, mux, clock and
macro-periphery cost. There is no selected compiler shape in the present cut.

## Buffered 1RW candidate: why a drain edge exists

Let edge **E** accept payload read R and write W together while reset is low.
Both protocol slots were empty before E, and both become pending after E.
The 1RW macro services R at E; W's address/data are captured into one buffer.
The P3 logical memory is the SRAM **overlaid by that buffered word**. Thus W
has entered P3 storage at E; its bytes are not discarded or acknowledged
before being captured. The buffer names an existing stage address and does
not create a second KV residency or an independent lifecycle owner.

Before edge **E+1**, neither request lane is ready, even if both responses
will be consumed at E+1. Therefore the macro services buffered W at E+1
without competing with a newly accepted payload operation. The buffer then
clears. Each collision creates at most one pending write and guarantees its
next-edge drain; this argument uses the actual no-consume/replace rule,
not average utilization or production's one-group bound.

| Edge / interval | Payload macro | Original external behavior to retain |
|---|---|---|
| E accepts R+W | Read R; buffer W | Same accepted requests and tags |
| After E | Macro Q supplies first-cycle read data; W bytes are in buffer | Read response and write ack valid at the original time |
| E+1 | Drain W; no new payload request can fire | Responses may be consumed or held; request-ready remains governed only by pending flags |
| After E+1 if read stalled | Held copy supplies the original response | Later writes must not perturb valid response data |
| Earliest subsequent acceptance | After the corresponding old response was consumed | Preserve the original empty-slot rule |

Macro read-Q must be available during the response cycle immediately after
the accepting edge. A fresh/held selector can expose Q in that first cycle
and capture it into the response-hold register at the following edge, before
a write changes Q. A macro with an additional registered latency cannot be
silently substituted. Actual clock-to-Q, output hold/write mode, read-to-hold
setup/hold and the output mux path need native timing checks at **2 ns**.

### Reset and fault discipline

- A previously buffered write drains at the next edge **even if synchronous
  reset is asserted there**. Reset may clear protocol slots, not lose bytes
  already captured into the logical P3 memory.
- If new read and write requests are both accepted on a reset edge, service
  the write directly; the read response is suppressed by the reference reset
  rule. Do not enqueue data into reset-cleared pending state.
- A stalled response retains its tag/data across later writes; after reset,
  old response-valid is cleared. SRAM bytes are neither scrubbed nor assumed
  zero-initialized.
- Parent faults, stage-generation checks, payload/sidecar completion,
  durability, publication and R6 handoff stay in the existing parent. The
  storage adapter cannot invent a later fault or a second completion point.

## Finite-model evidence and limits

[`../tools/check_p3_staging_storage_mapping_model.py`](../tools/check_p3_staging_storage_mapping_model.py)
compares independent reference and candidate states for two addresses and
binary word values. All four initial memories, arbitrary request/response
stall combinations, synchronous reset and both possible macro Q values on
writes are explored. Valid tags/data, ready/valid and the SRAM-plus-buffer
memory abstraction are checked. The sidecar is a separate independent write
resource and is **not enumerated** in this payload model.

The principal non-alias check reaches **160 states / 37,888 transitions**,
including 18,944 reset transitions, 512 simultaneous read/write transitions
and 3,840 deferred-drain transitions, with no mismatch. A separately labeled
old-data collision extension reaches **176 states / 42,240 transitions**;
that extension is not asserted to be the source Mem's collision contract.
Three negative controls produce counterexamples:

1. Read priority without storing W loses accepted bytes.
2. Clearing a deferred W on reset loses pre-reset memory contents.
3. Driving a stalled response from live macro Q allows a later write to
   corrupt that response.

The [model receipt](p3_staging_storage_mapping_model_20261106.json) includes
model hash, initial memories and replayable negative traces. These are
finite-domain abstract results, **not RTL equivalence, a parameter-general
proof, a physical macro model, or a new functional-suite pass**. Existing
P3 boundary tests exercise serial accesses/response holding, not this new
implementation. No candidate RTL exists in this batch.

## Cost coverage and required validation

| Cost term | Existing DC coverage | Required charge/evidence |
|---|---|---|
| Full payload and sidecar provision | Excluded P3 child | All macros, padding, port implementation, leakage and access energy |
| Existing 558 declared child protocol bits | Excluded with child body | Tags, valid flags, response holding and implementation logic; count once |
| Buffered 1RW additions | No implementation yet | One 512-bit write word + 15-bit address + valid = 528 bits, plus a fresh/held phase bit in the sketched organization; total adapter sketch 1,087 bits before macro internal state/other logic |
| Macro Q / output latches | No selected macro | Count within macro characterization; do not silently double-count as external holding |
| Access and response muxing | Excluded child / new implementation | Read/write steering, buffer enables, bank/width selection, hold selector, buffers and timing-driven sizing |
| Parent wrapper, compact tables, journal, ordering and publication | Already in accepted RD1 parent hierarchy | Retain; do not add their whole hierarchy a second time |
| Pending-HBM backing and packed position service | Separate external service | Keep outside P3 local SRAM price and nonzero/unestimated |

The 529 additional adapter bits are a source-level organization count, not a
mapped-area estimate. No area or power improvement is measured. A 1RW macro
may or may not yield the lowest total cost after periphery, muxes, padding,
timing and real availability. Historical M2 or S2 CACTI figures do not price P3.

Before any integration, the minimum validation is:

1. Build an isolated same-interface reference/candidate miter, retaining all
   capacity and full data/tag bits. Test first/last layer and fragment,
   simultaneous payload read/write/sidecar writes, independent blocked acks,
   repeated collisions, long-held reads with continued writes and both edges
   of every reset/drain case. Never change ready to hide a conflict.
2. Establish emitted-reference read/write collision semantics or a justified
   legal-parent restriction. Verify sidecar address arithmetic and all 64
   stored bits, and prove buffer-overlay/drain invariants on actual RTL.
3. Use a declared full-cost memory model; verify read latency, read-Q hold
   and synchronous-reset write behavior. Width-striped macros must accept
   all 512 bits together and cannot acknowledge partial lane completion.
4. Verify setup/hold and adapter paths under unchanged 2-ns constraints;
   charge every macro and adapter cell. A macro proxy is not physical signoff.
5. Run parent materialization/publication/fault/reset non-regression and
   source/port/hash checks before any separately authorized integrated run.

This assessment recommends the next **isolated equivalence** step; it does
not launch it, select a macro, modify a frozen interface, alter either remote
experiment, or establish PPA/system speedup/net hardware benefit.

The [assessment receipt](p3_staging_storage_mapping_feasibility_20261106.json)
records 24 static source/accounting checks, hashes of 18 source/evidence
artifacts and revalidation of all 32 previous-ledger input hashes. The two
existing P3 source-boundary guards pass; no functional simulator is run.
Document links, receipt consistency and `git diff --check` are checked before
the separate assessment commit.
