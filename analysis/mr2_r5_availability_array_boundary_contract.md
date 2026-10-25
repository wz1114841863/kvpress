# MR-2-R5 — availability/generation array-only boundary

**Status:** `functional_boundary_passed` (2026-10-25); independent of MR-1B
and of the separately required M2 production replacement.

## Scope

`RouteAR5AvailabilityArrayBoundary` holds only the logical R5
availability/generation vectors.  `RouteAPageManager` remains the unique owner
of page-allocation selection, PageRef formation, descriptor visibility,
append/reclaim sequencing, durable invalidate-before-free, allocator-release
observation, drain, reset/init, and all external descriptor-service traffic.

The child receives no ready/valid protocol and cannot create an allocation,
descriptor request, visibility fact, reclaim permit, release, terminal, or
retirement fact.  Its two inputs are observations of already accepted parent
events:

| Parent accepted event | Array-only effect | Control retained in PageManager |
| --- | --- | --- |
| `page_allocation_req_in.fire` | mark the parent-selected free page allocated; retain its generation | free search, request validation, PageRef/allocation response, build state and descriptor image |
| matching successful `reclaim_delivery_in.fire` | for each allocated lane in the selected descriptor line, clear availability and increment generation | R6 permit, exact R2/R1 terminal match, old-generation release observation, descriptor unreadability, fault/drain rules |

Reads of the child vectors remain PageManager-local control observations for
free search, PageRef/generation validation, descriptor-line invalidation data,
descriptor location checks, and drain assertions.  The boundary is a logical
functional reference split only: it selects no SRAM macro, banking, physical
ports, latency, controller, clock, timing, area, power, throughput, or PPA.

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
