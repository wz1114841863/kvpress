# R5 descriptor externalization — control-projection contract

**Status:** `implementation_in_progress` (2026-10-29).

## Purpose and boundary

`RouteAControlProjection` must not synthesize the functional
`descriptorEntryImage`, `descriptorReadable`, or `descriptorValidRecords`
backing that is retained by the bounded functional measurement DUT.  This
successor replaces that backing with the typed
`functional_r5_descriptor_service` top-level boundary.  It does not select a
descriptor macro, controller, bandwidth, latency, capacity, or energy model.
Those remain external and `nonzero_unestimated`.

R5 remains the owner of allocation selection, PageRef generation, stale
rejection, append/tail ordering, invalidate-before-free, availability update,
old-PageRef release, drain, and reset.  R3/R6 publication/authority remains
the existing upstream precondition for an internal packed-read lookup; R5
does not duplicate it in a per-page liveness table.  The service owns only
512-bit descriptor-line contents and returns checked service responses.

## `r5_descriptor_service_v1`

One ready/valid interface carries three operations rather than creating a
second maintenance channel:

| Operation | accepted request | required matching response | parent effect |
| --- | --- | --- | --- |
| `Lookup` | only for the already internal-authorized packed-read request and nonzero legal `valid_records` | exact identity, line, PageRef, count, `OK`, `found` | emits the existing R5 descriptor grant with returned payload/sidecar handles |
| `ReadLine` | append or reclaim state requires the original descriptor line | exact identity, line, `OK`; append new-page permits an empty line | holds the returned line privately to create one R2/R1 maintenance write |
| `CommitLine` | only after the matching existing R2/R1 terminal reports durable `OK` | exact identity, line, `OK` | append marks descriptor durable; reclaim may then update availability/generation |

The descriptor line is fixed at 512 bits / 64 B / four 128-bit entries.  A
`ReadLine` response carries a four-bit live mask solely so R5 can construct a
line invalidation image; it cannot allocate or release a page.  Mismatched,
stale, failed, or reset-interrupted responses are consumed fail-closed: no
lookup grant, publication progress, availability release, or inferred retry is
created.

`CommitLine` follows—rather than replaces—the pre-existing append/reclaim
R2/R1/core-memory transaction and its ordering.  Thus an append cannot meet
the descriptor-durability prerequisite until both the original R1 terminal and
the external commit acknowledgement are accepted.  A reclaim cannot advance
availability or release old PageRefs until the same ordered pair completes.

## Verification and exclusions

The bounded measurement DUT still uses the old functional backing and is
required to retain its prior R5/R3 behavior.  The projection-specific tests
must cover delayed response, ready-low, fault, stale/mismatch, reset, append
and tail-link commit, first packed lookup, and reclaim ordering.  The
projection must regenerate successor HDL and prove that the three functional
backing names are absent from its elaborated closure before the successor DC
feasibility run.

This is a control-projection replacement only.  It changes neither R3's
publication linearization point, R6 authority, R2 arbitration, the page size,
admission, pruning, GQA, nor scheduler behavior.  It is not a physical HBM
controller, memory macro, PPA result, or descriptor-service cost measurement.
