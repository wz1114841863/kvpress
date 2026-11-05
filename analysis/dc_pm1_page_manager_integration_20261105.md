# PM1 Page Manager integration candidate — 2026-11-05

## Scope

This is the bounded production-module integration successor to the two failed
test-only PM1 paired screens.  It does not repeat the DC 2018 mapping of the
36,720-primary-input flat baseline selector.

`RouteAPageManager` now has an explicit `bankAllocatedLineSelector` realization
parameter.  Its default is `false`, so every existing production instantiation
and the already frozen/running RD1 input remain byte-for-byte unaffected by
this candidate.  The PM1 test instance selects `true`.

When enabled, only
`PriorityEncoder(allocatedLine)` is replaced by the already verified exact
574-by-64 banked helper at the control-projection geometry.  The following are
unchanged:

- all 36,720 parent-owned `allocatedLine` bits;
- lowest-index reclaim ordering and empty-input guard;
- same-cycle `reclaimLine` capture;
- reclaim permit, delivery, terminal and availability-ack handshakes;
- descriptor/R5 authority and all external interfaces;
- pruning, admission, R3 publication, R6 authority and R2 arbitration.

## Functional validation

Local Java 21 validation completed:

- `Test / compile`: PASS;
- `RouteAReclaimSpec`: 5/5 PASS, one suite complete, zero aborts/failures.

The suite instantiates the real `RouteAPageManager` with PM1 enabled and covers
successful durable free, fault retention, multi-lane line invalidation, stale
terminal exclusion and ordered reclaim across two descriptor lines.  The
previous exact-selector bounded exhaustive and full 36,720-entry checks remain
the bit-level equivalence authority.

This establishes functional integration at the test geometry only.  It is not
a generated full-profile input, mapped-area or timing result.

## Measurement route

The next step is a read-only probe of the accepted saved production DDC to
determine whether `route_a_page_manager` remains an independently addressable
mapped design and whether its effective boundary/constraint context can be
preserved for a controlled replacement experiment.  No identical flat-selector
screen will be rerun.

If the saved DDC cannot support a controlled child replacement, the fallback
is a later complete same-fair-v1 Route-A successor run after RD1 completes.  A
standalone candidate child area must not be compared directly with an
overlapping saved-DDC fanin cone as though they were matched scopes.

No PPA, clock-load, external-service cost, system acceleration or hardware net
benefit conclusion follows from this candidate.
