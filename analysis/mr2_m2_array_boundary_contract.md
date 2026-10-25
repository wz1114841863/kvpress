# MR-2-M2 — bounded entry-array-only boundary

**Status:** `parent_access_adapter_implementation_in_progress`; follows bounded
functional M2 production entry-data integration and does not select a physical
macro.  The prior logical-boundary evidence remains valid; the present
successor replaces the parent whole-array functional views with explicit
logical accesses and is not yet a macro/physical conclusion.

## Scope

`RouteAM2EntryArrayBoundary` owns only the functional entry words:

- 288 logical head keys, each with two identical 128-bit head-control
  replicas; and
- 614 logical 128-bit span-owner entries.

The child now has one parent-facing `head_lookup_req`/`head_lookup_rsp`
`Decoupled` pair and two parent-owned, already decided `Valid` write lanes:
`publication_commit` writes both replicas and one span together, while
`handoff_release` clears those same entry locations together.  A lookup
response is registered and held until its consumer accepts it.  Each write
lane emits an exact `publication_commit_ack` or `handoff_release_ack` on the
following adapter cycle.  These acknowledgements only observe an already
accepted parent event; they are neither an extra publication point nor an
authority/fault path.

The child has no credit policy, allocator, authority,
publication decision, source selection, R2 request, R6 lifecycle action, or
external-memory traffic. Its vectors are a logical functional reference split,
not an SRAM macro, bank/port/latency choice, controller, timing, area, power,
throughput, or PPA result.

## Control retained in `RouteAM2ProductionControlOwner`

The parent remains the sole owner of accepted `MetadataAppendOperand` and
group-prepare association, immutable member/provenance validation, private
prepare state, head/span RMW decision, slot allocation, generation and stale
checks, credit, typed member response/fault, abort, reset, publication
candidate, and post-R6 handoff qualification. `metadataSlotOccupied` and
`metadataSlotGeneration` remain parent-local peripheral control state; they
are not a second copy of entry data.

| Existing accepted event | Explicit array-adapter effect | Parent-retained control |
| --- | --- | --- |
| private grouped prepare | issue one key-specific head lookup; hold the private preparation until the registered response is accepted | validate declaration/member shape, allocate slot, generation/stale and credit checks, derive exact RMW operand and decide typed member response |
| matching `metadata_publish_commit` / Published resolution | atomically write two prepared head words and one prepared span word; emit commit ack | validate both entries, private prepare, two member responses, publication decision and status |
| exact post-R6 all-member handoff observation | atomically clear the matching two head words and span word; emit release ack | provenance-index lookup/uniqueness, credit release, generation increment or fail-closed exhaustion |

The two write lanes may be active in one cycle only for distinct logical head
and span locations; the child asserts this non-alias condition and continuously
asserts head replica equality. This is a bounded semantic two-lane contract,
not a selected physical dual-port/macro implementation. The parent keeps a
small immutable visible-provenance index (slot, layer/head, stage generation,
tag and valid-record count) solely to qualify a later release; it does not
duplicate either 128-bit entry word. The parent may not write entry words on
member response, publication fault, abort, stale input, or reset; reset is the
child register's ordinary destructive initialization.

## Required verification

- structural guard proves the named boundary owns all head/span entry `RegInit`
  vectors, the production owner has none, and the owner uses explicit lookup
  and accepted-write ports rather than a whole-array view;
- direct `RouteAM2EntryArrayBoundarySpec` verifies lookup response holding
  under backpressure, exact commit/release acknowledgement, and released-word
  readback;
- existing production-owner tests preserve private-before-publication,
  two-member gating, typed abort, publication-fault nonvisibility, reset, and
  exact handoff release;
- selected W0/MR-1A/MR-1B/M2 and dual-DUT structural non-regression remains
  passing.

## Evidence

- Local boundary and peer-boundary structural guards: 5 passed on the adapter
  successor source, including
  `tests/test_mr2_m2_array_boundary.py`, plus all MBR/SRP manifest validators
  and `git diff --check`.
- The directed Chisel/Verilator adapter and production-owner suite is running
  on the successor source.  No adapter regression result is claimed until its
  completed test report and exit status are recorded.
- Remote targeted production evidence: 3 suites / 11 tests passed, `EXIT=0`,
  at
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_array_boundary_p0_20261023.log`.
- Remote selected cross-stage non-regression: 10 suites / 40 tests passed,
  `EXIT=0`, at
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_array_boundary_p1_full_nonreg_20261023.log`.

The latter covers the Full-KV contour, Route-A packed/hot/direct-pending
paths, four-consumer S2/GQA completion, M2 fixture-unit behavior,
production-owner and admission-bridge behavior, and the independent dual-DUT
structural guard. It is functional Chisel/Verilator evidence only.

This boundary does not close macro/port/latency/access mapping, queue/staging
activity evidence, DC, CACTI, PPA, or a physical M2 cost conclusion.
