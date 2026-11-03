# Route-A M2/P3 wrapper control-realization P0 diagnosis — 2026-11-03

## Scope and disposition

This is a read-only successor diagnosis of `route_a_m2_p3_wrapper` after the
accepted paired run `dc_feasibility_fair_control_refinement_20261102_r1`.  It
uses the saved DDC, native reports, generated SystemVerilog and current Chisel
source.  It changes no RTL, generated HDL, proxy, constraint or synthesis
artifact and launches no new synthesis.

The P0 disposition is:

```text
wrapper_hotspot_confirmed
+ compact_membership_record_is_first_bounded_candidate
+ materializer_selector_and_reconciliation_lookup_are_later_candidates
+ implementation_and_new_dc_not_started
```

All candidates preserve the existing Route-A mask, admission result, R3
publication boundary, R6 authority owner, R2 arbitration, page organization,
one-packer ordering and Full-KV comparison boundary.  This diagnosis does not
select a memory macro or port schedule, black-box parent control, relax the
2.0-ns fair-v1 clock, or establish PPA, external-service cost, speedup or
hardware net benefit.

## Read-only evidence closure

The accepted result already establishes that the wrapper is essentially
unchanged by the metadata-bridge refinement:

| metric | refined successor |
| --- | ---: |
| wrapper cell area | 2,968,610.1130 |
| share of Route-A cell area | 75.1% |
| wrapper combinational area | 1,265,427.0685 |
| wrapper noncombinational area | 1,674,027.4848 |
| wrapper mapped cells | 2,375,848 |
| wrapper mapped sequential cells | 476,140 |
| wrapper mapped combinational cells | 1,899,707 |

The read-only P0 probes used:

- saved DDC
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/dc_feasibility_fair_control_refinement_20261102_r1/route_a/route_a_control_projection.ddc`;
- native `area_hierarchy.rpt`, `timing_setup.rpt` and
  `check_design_postcompile.rpt` from the same immutable run;
- generated module
  `/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/control_refine_a6acd4a_p6/route_a_control_projection_split/route_a_m2_p3_wrapper.sv`;
- `RouteAM2P3Wrapper`, `AdmissionContext` and
  `PendingPayloadReadBinding` in the current source tree.

The DDC was only read and queried.  No compile/update/write command was run,
and the completed run directory was not modified.

## State concentration

### Generated logical state

The generated wrapper contains 990,322 logical register bits.  The two
36-layer by 64-record membership tables dominate it:

| generated state family | bits | share of wrapper raw state |
| --- | ---: | ---: |
| `membershipPayloadBindings` | 647,424 | 65.375% |
| `membershipEntries` | 308,736 | 31.175% |
| both membership record tables | 956,160 | 96.550% |
| `reconciliationBindings` | 17,984 | 1.816% |
| all other wrapper state | 16,178 | 1.633% |
| **total** | **990,322** | **100.000%** |

The raw widths agree exactly with the source/profile contract:

- one `AdmissionContext` is 134 bits;
- one `PendingPayloadReadBinding` is 281 bits;
- `36 * 64 * (134 + 281) = 956,160` bits;
- `64 * 281 = 17,984` reconciliation bits.

This is a generated-state and elaboration/lint surface, not a mapped-area
measurement.

### Mapped sequential state

DC already removes 514,182 of the wrapper's 990,322 raw state bits.  The saved
DDC retains the following membership fields:

| table / live field | mapped sequential cells |
| --- | ---: |
| `membershipEntries.entry_id` | 55,296 |
| `membershipEntries.layer` | 13,824 |
| `membershipEntries.kv_head` | 6,912 |
| `membershipEntries.logical_position` | 34,560 |
| `membershipEntries.payload_ref` | 147,456 |
| **mapped `membershipEntries`** | **258,048** |
| binding transaction identity | 11,520 |
| binding payload handle/address | 147,456 |
| binding source generation | 18,432 |
| binding destination endpoint | 6,912 |
| **mapped `membershipPayloadBindings`** | **184,320** |
| **both mapped membership tables** | **442,368** |

The two tables are 92.907% of the wrapper's mapped sequential cells.  With
the 17,984-bit reconciliation journal, these three structures account for
460,352 cells, or 96.684%.

DC removes the membership context's stored group tag, ordinal and valid-count
fields, and removes every duplicated common membership field plus both M2
mapping fields from `membershipPayloadBindings`.  Therefore simply replacing
the two source bundles by a merged bundle can reduce raw HDL and lint but
cannot claim the corresponding mapped-state reduction: DC has already done
most of that pruning.

## First bounded candidate: compact internal membership record

The admission join already proves, before state is written, that:

- `layer` equals the selected 36-bank index;
- `kv_head` equals `stageHead(layer)`;
- group tag and valid-record count equal `stageTag(layer)` and
  `stageValidRecords(layer)`;
- member ordinal equals the table index;
- `entry_id = logical_position * 288 + layer * 8 + kv_head`;
- the pending binding's common membership fields equal the accepted admission
  context.

The wrapper consumers then require only:

```text
member record: logical_position[14:0] + payload_ref[63:0]       = 79 bits
pending suffix: transaction_identity[4:0] + handle[63:0]
                + source_generation[7:0] + destination[2:0]    = 80 bits
```

All externally visible fields can be reproduced from those 159 per-record
bits plus the existing bank/index and stage header state.  In particular,
`entry_id` is reconstructed only for the post-publication member/authority
observation; it need not be inserted into admission ready logic.

If implemented without any other change, the structural accounting is:

| quantity | current | compact candidate | delta |
| --- | ---: | ---: | ---: |
| raw two-table state | 956,160 | 366,336 | -589,824 |
| total wrapper raw state | 990,322 | 400,498 | -589,824 (-59.559%) |
| currently mapped two-table state | 442,368 | 366,336 | -76,032 |
| wrapper mapped sequential cells, pre-DC accounting | 476,140 | 400,108 | -76,032 (-15.968%) |
| Route-A mapped sequential cells, pre-DC accounting | 653,138 | 577,106 | -76,032 (-11.641%) |

The 76,032-cell value is the meaningful mapped-state ceiling: it is exactly
the currently retained `entry_id`, `layer` and `kv_head` copies.  The larger
589,824-bit source reduction is useful for generated size and lint, but is not
a mapped-area forecast.  Cell area, combinational area, clock load and timing
still require another same-fair-v1 native DC comparison.

### Required semantic checks

A P1 implementation must demonstrate all of the following before generation:

1. admission still compares every original field and accepts the context,
   authority transition and optional pending binding atomically;
2. ordinary historical admissions without a pending binding still work;
3. materialized work and sidecar outputs reproduce the exact payload,
   position, transaction and pending-location facts;
4. fragment and sidecar validation use the same immutable association;
5. publication emits the exact original entry/layer/head/position/payload/tag
   and ordinal, under ready-low as before;
6. pending-to-packed withdrawal and late reconciliation retain their full
   original binding in this first batch;
7. publication remains the only authority/visibility linearization event and
   no new issue/arbitration policy is introduced.

## Combinational structure and timing

The current materializer builds 36 independent 64-bit candidate masks.  Each
mask combines membership-present, binding-present, not-materialized, a
variable valid-record mask and stage eligibility.  It then priority-encodes a
layer and ordinal and dynamically selects wide member/binding records.
Generated elaboration contains repeated 64-way muxes, including multi-kilobit
intermediate mux outputs.

This network is timing-relevant, not merely large.  Eighteen of the 20 paths
listed in the refined native setup report explicitly start or end in `m2P3`.
Most terminate at `materializedMembers` or `stageState`.  One reported path
starts at `m2P3/stageValidRecords_24_reg[0]` and reaches the functional
sidecar allocation ready output through the variable-mask shift/subtract and
candidate-selection logic.  The wrapper therefore remains both the dominant
area owner and a major setup-violation surface.

After membership compaction, a separate selector batch may replace the
current expression by an equivalent per-layer unissued-binding mask plus a
36-bit eligible-stage summary, selecting only one 64-bit bank and one compact
record.  It must preserve the existing lowest-layer/lowest-ordinal choice and
ready/valid holding behavior.  A registered selection or extra service cycle
is not automatically allowed because it can change candidate arrival and R2
behavior.

## Reconciliation lookup candidate

The reconciliation journal is only 17,984 sequential bits, so it is not the
first state target.  However, the current lookup compares the request against
all 64 full 281-bit records and priority-encodes the match.  Ingress already
stores each binding at its validated `group_member_ordinal`, asserts that the
slot was unused, and the lookup registration carries that same ordinal.

A later, separately checked batch can use the ordinal as the journal index
and perform the same full equality check against exactly that indexed record.
This retains fail-closed matching and the full late-registration/withdrawal
carrier while replacing a 64-record CAM-like comparison with one indexed read
and one comparator.  It is primarily a combinational-area/lint candidate, not
a 17,984-bit state-removal claim.  Compacting or deleting the persistent
journal is not approved by P0 because it survives publication for late
registration and is the withdrawal carrier.

## Structural cleanliness

The wrapper itself still reports 528 `LINT-28`, 109 `LINT-29`, 143 `LINT-31`
and 58 `LINT-52` records.  Samples are typed unused carrier fields,
input-to-output feedthroughs and shared output connections.  They should be
recounted after structural refinement, but warning removal is not authority to
delete required ports, collapse owners or tie off a real parent control path.

## Ordered successor batches

### P1 — compact membership realization

Implement only the internal 79-bit member record and 80-bit pending suffix,
reconstructing validated fields at their consumers.  Keep external bundles,
the reconciliation journal, masks, selection order, handshakes and all owners
unchanged.  Expected source accounting is 400,498 wrapper raw bits; the native
mapped question is whether the 76,032 currently retained redundant cells and
their clock load disappear without timing or lint regression.

Required gates before any DC launch:

- focused R3 materialization, pack-read, R3/R5 publication and
  admission/publication integration tests;
- the existing directed production set, four full-root tests and 41-test
  cross-stage non-regression set;
- 48-file successor closure, 16 typed port families, 12 production owners and
  5/5 paired array proxies;
- generated raw-state recount and proof that all public port families and
  parent controls remain present;
- `git diff --check` and a standalone commit.

Only after those gates pass should a separately authorized same-fair-v1 DC run
be started in tmux.  Acceptance must again be split into tool/input closure,
mapped area, timing and structural cleanliness.  The fixed comparison point is
the accepted refined run, not the older pre-refinement Route-A result.

### P2 — equivalent materializer selection network

After P1 is independently closed, simplify the 36-by-64 candidate construction
and wide dynamic selection without changing priority, one-active-member
behavior or R2 ownership.  Treat any added register or cycle as a semantic
change requiring explicit review, not as a free timing fix.  Run and commit
this as a separate batch.

### P3 — ordinal-indexed reconciliation lookup

Replace the 64-way full-record match only after proving the production
single-group/unique-ordinal invariant at the lookup boundary.  Retain the
full equality check and persistent journal.  This is also a separate test,
generation and DC batch.

## Non-conclusions

P0 establishes that further bounded control-realization refinement is
plausible and localizes three structures.  It does not establish their final
mapped area or timing benefit, select a macro/controller, make external
services free, close setup, clean lint, or prove PPA, power, system
acceleration or net hardware benefit.
