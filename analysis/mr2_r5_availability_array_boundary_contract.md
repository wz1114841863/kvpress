# MR-2-R5 — availability/generation array-only boundary

**Status:** `parent_access_adapter_functionally_verified` (2026-10-26);
independent of MR-1B and of the separately required M2 production replacement.

## Scope

`RouteAR5AvailabilityArrayBoundary` holds only the logical R5
availability/generation vectors.  `RouteAPageManager` remains the unique owner
of page-allocation selection, PageRef formation, descriptor visibility,
append/reclaim sequencing, durable invalidate-before-free, allocator-release
observation, drain, reset/init, and all external descriptor-service traffic.

The child cannot create an allocation, descriptor request, visibility fact,
reclaim permit, release, terminal, or retirement fact. It owns only the
availability/generation words behind `r5_availability_access_v1`; the parent
selects every key and accepts each typed result. It exposes one registered
keyed lookup, an allocation-update acknowledgement, and a multi-lane reclaim
generation-update acknowledgement:

| Parent event / access | Array-only effect | Control retained in PageManager |
| --- | --- | --- |
| parent keyed `availability_lookup_req.fire` | return the exact registered `{page_id, allocated, generation}` response and hold it under ready-low | scan progression and first-free selection; no macro-side allocator |
| accepted `page_allocation_req_in.fire` with the parent scan's free key | mark that selected page allocated and return its generation in `allocation_update_ack` | request validation, free scan, PageRef/allocation response, build state and descriptor image; outward response waits for ack |
| matching successful `reclaim_delivery_in.fire` | receive the parent-selected line update, then return every lane's old generation and allocated mask while clearing/incrementing allocated lanes | R6 permit, exact R2/R1 terminal match, old-PageRef release observation, descriptor unreadability, fault/drain rules; reuse waits for ack |

`RouteAPageManager` has no whole-array `allocated_view` or `generation_view`.
It retains only descriptor-line reclaim scheduling state and the existing
external descriptor-service proxy; free search is a bounded parent-side keyed
scan, descriptor validation uses the existing descriptor image, and release
facts come only from the typed reclaim ack. The boundary selects no SRAM
macro, banking, physical port count, latency, controller, clock, timing, area,
power, throughput, or PPA.

The functional `descriptorEntryImage` remains in PageManager as the already
declared external descriptor-service proxy.  It is explicitly not an R5 local
SRAM-array proxy.  M2 is outside this batch: its current reference protocol
provider must first be replaced by a production owner before any M2 storage
interior can be isolated.

## Required verification

The R3/R5 directed specification uses narrow, test-only simulator probes around
the unchanged production owners.  The probes keep the publication/reclaim
channels under test, but terminate unobserved packed-write and pack-read
candidate carriers inside the probe.  This is necessary because the remote
ChiselSim DPI bridge cannot generate accessors for B2c's deeply nested
direct-pending association field when an otherwise unused full carrier is a
simulation-root port.  It is a harness boundary only, not an R3/R5 RTL tie-off
or a replacement for the production connection.

- structural guard proves that availability/generation state is owned only by
  `RouteAR5AvailabilityArrayBoundary`, while PageManager retains no direct
  availability/generation `RegInit` vectors;
- `RouteAReclaimSpec` preserves success, fault, stale, multi-lane, and
  generation/reuse behavior;
- `RouteAR3R5PublicationSpec` preserves allocation, descriptor durability and
  publication/reclaim ordering;
- applicable Route-A W0/MR-1A and MR-1B non-regressions remain passing.

No result from this work validates a physical R5 macro or descriptor HBM
service, nor changes R3 publication, R6 authority, R2 ordering, page size,
admission, pruning, GQA, or scheduler semantics.

## Verification record

- Local array-boundary structural guard passed (`2/2`), proving that only
  `RouteAR5AvailabilityArrayBoundary` owns the availability/generation vectors
  and that `RouteAPageManager` retains the parent control effects.
- Remote R5 directed evidence passed (`6` suites / `21` tests, `EXIT=0`) at
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_r5_final_p0_directed_final_20261024.log`.
  It covers allocation, descriptor-private-to-visible publication ordering,
  successful/faulted/stale/multi-lane reclaim, generation reuse, R1/R2/R5/R6
  terminal/reclaim, reset, and packed R5-to-S2 descriptor facts.
- The init/reset harness correction was also separately verified (`2` suites /
  `6` tests, `EXIT=0`) at
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_r5_init_reset_fix4_20261024.log`.
  It exposes an existing but inactive outer payload-binding port so Verilator
  cannot constant-fold an unrelated admission comparison; it changes neither
  the production owner graph nor payload-binding behavior.
- Latest-source selected cross-stage evidence passed in two non-overlapping
  invocations: `3` suites / `13` tests (`EXIT=0`) at
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_r5_p1_full_nonreg_20261024.log`,
  and `7` suites / `27` tests (`EXIT=0`) at
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_r5_p1_missing_nonreg_20261025.log`.
  Together these are the selected `10` suites / `40` tests covering Full-KV,
  Route-A packed/hot/direct-pending, S2/GQA completion, M2 owner/bridge and
  fixture separation, and the dual-DUT structural guard.
- Parent-side access-adapter evidence on successor `3aab1ce` passed `4`
  suites / `15` tests in two remote invocations: direct keyed
  availability/ack contract plus reclaim (`1/1` and `5/5`) at
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/r5_parent_adapter_directed_f4b35ca_rerun.log`,
  then R3/R5 publication and reset (`5/5` and `4/4`) at
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/r5_parent_adapter_pubfix_3aab1ce.log`.
  These verify response holding, ack-derived PageRef/reclaim generations,
  publication-before-visibility, fault fail-closed behavior, and reset
- The selected current-source cross-stage regression is now complete on the
  unchanged R5 production RTL of `f4b35ca`: `10` real suites / `40` tests,
  `EXIT=0`. The initial invocation on `a60e525` ran six real suites / `23`
  tests; four incorrectly package-qualified selectors produced `0/0` and are
  explicitly excluded. Correct-package reruns contributed four-consumer and
  packed-composition `6/6` at
  `r5_parent_adapter_p1_missed_suites_a60e525.log`, then owner-fact and
  direct-pending `11/11` at
  `r5_parent_adapter_p1_owner_direct_bfa441c.log`. Commit `bfa441c` changes
  only the owner-fact test to wait for the contract-required allocation ack;
  it does not alter production RTL. This completes the R5 batch's
  current-source selected non-regression, but not any successor source/port
  freeze, macro, or physical-realization decision.
