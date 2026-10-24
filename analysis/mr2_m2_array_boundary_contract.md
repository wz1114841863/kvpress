# MR-2-M2 — bounded entry-array-only boundary

**Status:** `functional_boundary_passed`; follows bounded functional M2
production entry-data integration and does not select a physical macro.

## Scope

`RouteAM2EntryArrayBoundary` owns only the functional entry words:

- 288 logical head keys, each with two identical 128-bit head-control
  replicas; and
- 614 logical 128-bit span-owner entries.

The child accepts two parent-owned, already decided `Valid` updates: a
publication commit that writes both replicas and one span together, and an
all-member handoff release that clears those same entry locations together.
It has no ready/valid service protocol, credit policy, allocator, authority,
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

| Existing accepted event | Array-only effect | Parent-retained control |
| --- | --- | --- |
| matching `metadata_publish_commit` / Published resolution | atomically write two prepared head words and one prepared span word | validate both entries, private prepare, two member responses, publication decision and status |
| exact post-R6 all-member handoff observation | atomically clear the matching two head words and span word | lookup/uniqueness, credit release, generation increment or fail-closed exhaustion |

Both ports may be active in one cycle only for distinct logical head and span
locations; the child asserts this non-alias condition and continuously asserts
head replica equality. The parent may not write entry words on member response,
publication fault, abort, stale input, or reset; reset is the child register's
ordinary destructive initialization.

## Required verification

- structural guard proves the named boundary owns all head/span entry `RegInit`
  vectors and the production owner has none;
- existing production-owner tests preserve private-before-publication,
  two-member gating, typed abort, publication-fault nonvisibility, reset, and
  exact handoff release;
- selected W0/MR-1A/MR-1B/M2 and dual-DUT structural non-regression remains
  passing.

## Evidence

- Local boundary and peer-boundary structural guards: 8 passed, including
  `tests/test_mr2_m2_array_boundary.py`, plus all MBR/SRP manifest validators
  and `git diff --check`.
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
