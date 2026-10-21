# MR-2-R5 — availability/generation array-only boundary

**Status:** `implementation_pending_verification`; independent of MR-1B and
of the separately required M2 production replacement.

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
