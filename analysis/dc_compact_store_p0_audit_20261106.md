# Compact-table STORE P0 audit — 2026-11-06

## Scope and disposition

This is a source/contract read-only audit of the two compact R3 tables at
`4b64d2d44e877e4bac45c2449fbad16065fe6f8e`. Only this report, its field CSV,
source-evidence JSON and live navigation are added/updated. No RTL, tests,
generated HDL, synthesis scripts, constraints or frozen input is changed.
No SSH, tmux operation, simulator or DC process is invoked. RD2's frozen
inputs and run are untouched; its completion is not inspected in this batch.

The disposition is:

- No existing contract permits shortening either 64-bit value by truncation,
  alignment, base-plus-offset, or reconstruction from the other value.
- There is a concrete duplicate-storage candidate: the existing R3-owned
  64-entry reconciliation journal retains the same accepted suffix fields.
  Reusing its immutable fields deserves a separately scoped equivalence study.
- Current production admits at most 64 bound members of one layer per reset;
  this is a hardware-enforced ingress bound, not the generic wrapper capacity.
- The generic wrapper retains 36 x 64 unbound-member capability. Its journal's
  cross-bank ordinal uniqueness is an assertion, not an admission ready guard.
  These distinctions block an unconditional two-table replacement by 64 slots.

These are source/information-lifetime findings, not a new functional pass,
formal reachability proof, mapped saving, timing result, PPA or net benefit.

## Evidence and source anchors

All paths below are relative to the repository. Source SHA-256 values and the
15 static source checks are recorded in
[`dc_compact_store_p0_evidence_20261106.json`](dc_compact_store_p0_evidence_20261106.json).
Field-by-field inventory:
[`dc_compact_store_p0_fields_20261106.csv`](dc_compact_store_p0_fields_20261106.csv).

| Evidence | Source anchor |
|---|---|
| Field declarations | `hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala:2424` and `:2434` |
| Physical tables, presence and persistent journal | same file `:2555` through `:2566` |
| Atomic member/suffix/journal writes | same file `:2651` through `:2714` |
| M/S/C/F/B readers | same file `:2727` through `:2937`; prior read-port CSV |
| O, R6 handoff, withdrawal and late lookup | same file `:3306` through `:3469` |
| One-group ingress and no rearm | same file `:1295` through `:1548` |
| Production wiring and projection inheritance | `hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAMeasurementDut.scala:299` and `:447` |
| Producer and representation contract | `analysis/rtl3_9_a0_pending_payload_read_association_contract.md`; `analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md:58` |
| Journal lifetime and production limit | `analysis/mr1b_direct_pending_cross_owner_contract_proposal.md:620` through `:674` |
| Previously measured storage | `analysis/dc_compact_wrapper_hotspot_attribution_20261104.md` |
| Accepted whole-top RD1 result | `analysis/dc_rd1_full_paired_dc_result_20261106.md` |

Prior mapped attribution found exactly 182,016 member-table cells and 184,320
suffix-table cells, approximately 1,292,433 combined cell area in that
pre-RD1 mapping. This audit does not rerun that mapped-netlist attribution or
assign its rounded per-field areas to a future realization. RD1's accepted
whole-top area is 3,388,597.345862, with 577,106 sequential cells unchanged.

## Representation and the two 64-bit values

| Field family | Bits/record | 36 x 64 bits |
|---|---:|---:|
| logical position | 15 | 34,560 |
| payload reference | 64 | 147,456 |
| transaction identity (request 3 + incarnation 2) | 5 | 11,520 |
| pending handle/address | 64 | 147,456 |
| source generation | 8 | 18,432 |
| destination endpoint | 3 | 6,912 |
| total | 159 | 366,336 |

The total is 44.71875 KiB; the two 64-bit values contribute 294,912 bits,
80.503% of table data. Presence masks, headers, journal, read/write networks
and clock/peripheral costs are additional.

`payload_ref` originates at the external frontend lifecycle port. R6 latches
it as `controlPayloadRef` and relays it in AdmissionContext. The pending owner
must offer the same reference in PendingPayloadReadBinding, but supplies
`payload_handle_or_address` independently through the explicit top-level
pending binding port. The ingress checks common coordinates/reference/group
fields and copies the binding; neither producer is implemented here as a
base/stride address generator. R3 checks these immutable facts and copies
them on the same admitted edge. ReadIssueCandidateAdapter later copies the
handle into the core-memory request address; the reference travels separately
in the P3 target descriptor and returned fragment association.

The following reductions therefore have no current proof:

1. **Replace reference with entry_id or position.** The coordinate equation
   constrains entry_id only. There is no equation constraining payload_ref.
2. **Use reference as pending address.** A0 expressly forbids deriving the
   handle from payload_ref. The existing materialization test even uses
   reference 99 and handle 0x55. Small test constants do not bound high bits.
3. **Drop low alignment bits or upper address bits.** This is an opaque handle
   interface, not a selected aligned physical address format. The declared
   5-GiB cold pool does not specify a handle base, encoding or bit range.
4. **Group-shared base plus short offsets.** Only M2 mapping reference/owner
   are checked group-constant. Pending handles, identity, generation and
   destination are not checked constant or affine across members. The ingress
   unit test varies identity and handle between members of the same group.
5. **Hash or dictionary tag alone.** Exact comparisons must distinguish all
   64-bit values. A hash needs collision handling/full backing; 64 independent
   distinct values still require their full values somewhere. A small index
   helps only if that backing is already retained and correctly associated.

For example, changing only bit 63 of a matching external reference or handle
does not violate a width/range rule in the current admission predicates;
later exact output/equality paths can distinguish it. A short index without
backing loses that distinction. This is a source/contract counterexample
argument, not newly executed RTL stimulus.

## Per-field lifetime

Every member-table write is on accepted context/authority admission. Every
suffix write additionally requires an offered, matching binding; that same
edge writes the complete binding into the persistent journal. Reads use
pre-edge register data; presence exposes the new member on the next cycle.

| Data | Consumers and last-use boundary | Current invalidation / caution |
|---|---|---|
| member position | S sidecar, B exact position validation, O member observation and entry_id reconstruction for R6 | Keep through independently backpressured member and authority acceptance for that ordinal; the group presence mask clears only after the final ordinal completes both |
| member reference | M work, S sidecar, C work validation, F fragment association, B sidecar validation, O member observation | Publication acknowledgement is not final use: O reads the table afterwards. Keeping through both O handshakes is conservative and safe for the observation consumer |
| suffix request/incarnation | M output and C exact identity validation | Cannot release at M.fire: C is independent in the generic wrapper and still checks any present ordinal while RESERVED/FILLING |
| suffix handle | M output and C exact handle validation | Same lifetime as other suffix fields; the downstream request carries a copy, but that does not remove C's validation requirement |
| suffix source generation | M output and C exact stale-generation validation | Not derivable from P3 generation; no early reuse on an R1 request alone |
| suffix destination | M output and C exact endpoint validation | No group-wide constant guarantee; preserve independent arbitrary checked work |
| journal copies of all these fields | full late-registration equality and exact withdrawal on accepted R6 transition | Persist after publication, all-member handoff and runtime retirement; invalidated only by destructive reset |

M and C are the only suffix-table readers. They are qualified by
RESERVED/FILLING/presence conditions; C's ready is evaluated even when its
input valid is low. A future last-use proof must preserve that continuous
ready behavior, not only accepted transfers. No per-member suffix presence
bit is cleared on M.fire or on response completion. The binding-presence mask
is cleared on claim/reset; unlike membershipPresent, it is not cleared on
final observation. Its remaining bits in an EMPTY or observing bank are not
live pack-read permissions.

The ordinary completed/faulted path disables suffix consumers, but P0 does
not establish an unconditional early-free event from a state value alone:
pending child acknowledgements, simultaneous events and state-update priority
must be included in any future proof. Consumer backpressure can extend useful
lifetimes arbitrarily in cycles. There is no finite cycle-age reclamation
bound here. Fault or retirement does not erase the journal's late-lookup duty.

## Maximum simultaneous live records: three different boundaries

| Boundary | Member position/reference | Suffix fields | Meaning |
|---|---:|---:|---|
| Physical current wrapper declaration | 2,304 slots each | 2,304 slots each | Actual register allocation, independent of occupancy |
| Generic wrapper, packing-only admissions | Up to 2,304 retained records | No suffix for unbound records | Each of 36 banks can accept up to 64 unbound records; hold filling/observation to retain them |
| Generic wrapper, no journal-reuse assertion violations | Up to 2,304 total records | At most 64 bound admissions per reset | Every binding permanently consumes its ordinal in the global 64-entry journal; this is a conditional legal-trace bound |
| Actual production measurement/projection ingress | At most 64 records of one layer per reset | At most 64, always joined with a binding | Enforced by StateCollect, one immutable group layer, ordinal presence guard, and terminal StateDone |
| Persistent reconciliation journal | Up to 64 full bindings | Same 64 full bindings | Bound is cumulative per reset; values remain after compact-record final use |

These are analytic upper bounds/source witnesses, not measured workload
occupancy, a 64-member end-to-end liveness proof, or formal reachable-state
coverage. The 2,304 unbound-member storage witness needs no suffix journal
entry: claim each bank, accept distinct ordinals with matching authority and
binding.valid low, and withhold filling. The production bound follows a
different composition and cannot be substituted for that wrapper contract.

The production induction is: reset starts StateCollect with zero present bits;
each accepted ordinal is in range and previously absent; all members share
the first member's layer/head/tag/count; complete collection leaves StateCollect;
relay visits each stored ordinal once; the last relay sets StateDone. There is
no assignment returning to StateCollect before reset. The real top has no
alternate claim/admission ingress to R3. One pack engine or one live memory
transaction alone would NOT prove this bound; the ingress FSM does.

The journal bound requires special care. At `:2711`, duplicate ordinal is
asserted only after admission fires. `admissionJoinReady` does not test
reconciliationPresent. Two banks can otherwise pass the local admission
checks for the same bound ordinal, then fail this assertion. Thus the journal
does not provide general hardware-enforced overflow rejection. A future
optimization must specify its equivalence domain and prove the production
bound; adding a new admission gate is not authorized by this audit.

## Concrete storage opportunities and gates

### ST1: reuse immutable suffix fields from the existing R3 journal

On a bound admission, the same original four suffix values are written both
to `(layer, ordinal)` and to `reconciliationBindings(ordinal)`. The latter is
already required for exact late lookup and withdrawal and is never evicted
within the reset epoch. For assertion-valid no-reuse histories, this yields
the candidate invariant:

```text
live_bound_member(layer, ordinal)
  => journalPresent(ordinal)
     && journal binding identifies that accepted layer/member
     && compactSuffix(layer, ordinal) == journalSuffix(ordinal)
```

This is a strong source-level proof obligation, not completed RTL equivalence.
It suggests replacing duplicate suffix data with read-only views of the
existing R3 ledger. It does not move R6 authority, R3 publication, or admission
decisions, introduce a new external service, or discard any 64-bit value.
Per-bank logical presence/header qualification must remain. Preserve journal
lookup bypass precedence and withdrawal payload exactly.

Two alternative payload-only accounting endpoints, never additive:

- a separate 64 x 80 pool replaces 184,320 suffix bits with 5,120, a
  179,200-bit declaration delta before tags/pointers/peripheral costs;
- reuse of the already required journal could eliminate the separate 184,320
  suffix bits without a new payload pool, but adds read demand/fanout to the
  journal and still needs all association and reset logic.

Neither is a predicted mapped-area reduction. New muxes, drivers, owner tags,
buffering or replication for timing may offset savings. Multiple logical
readers cannot be serialized merely because they now use one backing store.
The generic cross-bank duplicate-ordinal assertion case must be explicitly
classified; treating an assertion as a ready gate is unacceptable. If scope
is limited to the production composition, that specialization requires
explicit review and compositional proof before implementation.

### ST2: member-record canonical backing needs stronger scope closure

For a bound member, the journal also retains position/reference and accepted
coordinates. Production joins every member with a binding, so a common
canonical R3 record is a real future direction. However, unbound generic
packing members do not enter the journal and remain legal. Replacing the
entire 36 x 64 member table by 64 journal slots would lose their capacity.

Keep the generic member backing unless a separately reviewed realization
preserves that capability or explicitly proves a production-only specialization.
A 36 x 64 membership mask/header interface may remain even with pooled data;
logical layer identities must not collapse. Do not claim this narrow
reset-only contour supports continuous multi-group operation or other models.

### ST3: physical storage remains a separate study

An RF/SRAM/banked-memory alternative can retain arbitrary full-width values,
but must account for storage, ports, decode, peripheral and clock costs. The
present combination of asynchronous selection, independent C/F/B ready checks,
M/S/O per-bank sharing, simultaneous readers and pre-edge writes must be
preserved or separately reviewed. No free proxy, extra cycle, capacity change
or new R2 arbitration is selected here.

Hardcoded `stages = 36`, the 288/8 coordinate equation and anchor widths show
that parameterization is incomplete. Page capacity 64 is an architecture
choice; 36 is the model anchor; the 64-bit fields are interface choices.
Separating these would improve portability but cannot itself reduce this
same-configuration area. The planning gap is failure to exploit/reconcile
storage representation and actual concurrency early enough, not evidence
that KVzap requires these particular register arrays.

## Validation and next decision

The local source/arithmetic audit checks 15 source conditions: bank/record
geometry, one-shot ingress initialization/no rearm, final StateDone, ordinal
and layer guards, the single journal write and no runtime clear, duplicate
assertion versus admission gate, exactly two suffix readers plus its write,
all four suffix assignments, final member-presence clear, no M.fire suffix
clear, and no materializedMembers condition in checked-work legality.
All pass. All seven field widths sum to 159 and reproduce the 366,336-bit
allocation; source/evidence hashes and CSV values recheck independently.
These checks inspect source text; they are not HDL simulation or formal proof.

No Chisel build, regression, new synthesis or macro evaluation is appropriate
for this documentation-only batch. `git diff --check`, local document-link
validation and unchanged source SHA checks are required before commit.

Recommended next decision: authorize an ST1 proof/isolated experiment plan,
with the generic/production equivalence domain resolved first. Include high-bit
sentinels, independently varied suffix fields, arbitrary nonzero layers, all
ordinals including 63, concurrent readers, pre-edge admission, valid-low ready,
held outputs, stale/absent binding, reset, late registration, withdrawal and
unbound packing non-regression. Reusing journal data must not redefine or
remove its existing persistence duties. Keep RD2 separate; choose a cumulative
integration successor only after independent evidence. This P0 starts none of
those experiments and accepts no numerical hardware benefit.
