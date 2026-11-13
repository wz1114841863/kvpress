# Gate-A R2 — core-side arbitration and dependency closure

## Status and boundary

**Status:** `complete_pure_software_core_side_eligibility_and_grant_contract; pre_rtl_only`.

R2 closes the pre-`core_mem_if_v1` eligibility and deterministic issue policy
for the selected anchor.  It does not reopen A4 scheduler, pruning, admission,
mask, M2 FIFO/ownership/dependency/credit, or atomic-publication semantics. It
does not model HBM scheduler policy, controller arbitration, cycles, latency,
throughput, bandwidth, energy, PPA, RTL, or model/GPU execution.

## Selected issue structure

```text
frozen FIFO / ownership / dependency / credit predicates
                    + source-specific safety predicates
                                  |
                                  v
                         dependency scoreboard
                                  |
                                  v
                       eligible read-class set
                                  |
                                  v
        rotating-priority core-side read grant -> core_mem_if_v1
```

The rotating class order is fixed as:

```text
s2_fill -> direct_pending -> pack_read -> s2_fill
```

For each class, only the smallest `(arrival_ordinal, candidate_id)` among its
eligible candidates may be selected.  This preserves every required FIFO
predecessor supplied by the frozen semantic contract.  The cursor advances
only after R1 accepts the request.  If R1 ready is low, no candidate, cursor,
mask, admission disposition, ownership, or credit state changes.

This gives weak fairness only among continuously eligible classes at successful
core-side grant opportunities.  It is not a response-latency, bandwidth,
deadlock-freedom, or sustained-service guarantee.

The anchor has one pack write path.  It has no competing core-side payload
write class, so its gate is an eligibility predicate rather than a second
performance arbiter.  R5 descriptor maintenance is additionally represented
as a separate FIFO-ordered `desc_maint_write` channel that uses the *same* R1
write boundary.  It is deliberately outside the frozen payload-read rotation
and cannot advance or reclassify `s2_fill -> direct_pending -> pack_read`.
R5 has no selected descriptor-read operation, so no synthetic `DESC_READ`
class is introduced.  External controller behavior remains outside R2.

## Eligibility guards

All read candidates require frozen FIFO predecessor satisfaction, ownership,
logical credit, and a ready destination.  In addition:

| Candidate | Required source-specific condition |
|---|---|
| `s2_fill` from packed cold storage | Associated metadata publication is visible. |
| `s2_fill` from Full-KV | No Route-A metadata-publication guard. |
| `direct_pending` | Referenced pending payload remains authoritative. |
| `pack_read` | Referenced pending payload remains authoritative and its P3 stage is ready/owned. |
| `pack_write` | FIFO/ownership/credit, page allocation, complete P3 stage data, and P3 stage ownership all hold. |
| `desc_maint_write` | FIFO/ownership/credit for one R5 descriptor line; exactly one 64-B R1 write fragment. |

`pack_write` receives a successful R1 `write_commit` only after its complete
ordered data sequence.  That event establishes payload durable only.  R2 may
mark the associated metadata publication group eligible only after the R1
reference has recorded that same write as durable.  The later M2 publication
still performs the single frozen atomic authority handoff; R2 does not publish
metadata itself.

Faulted writes never enable publication.  A stalled or ineligible candidate
remains delayed; it is never dropped, reclassified, retried, converted to
Full-KV, or used to change a mask/admission decision.

`desc_maint_write` receives the same R1 identity, ready/valid, reset-epoch,
and exactly-one terminal rules as every other R1 write.  Its successful commit
means descriptor-line durable only.  It cannot itself expose packed traversal,
release pending authority, or substitute for `metadata_publish_commit`.

## Executable reference

`kvpress/route_a_arbitration_reference.py` implements the event-level
scoreboard and core-side grants.  It calls the R1 wrapper only after a
candidate is eligible, and it requires the R1 durable latch before accepting a
successful write-commit dependency.  Its tests cover source-specific guards,
same-transaction ordering through R1, cross-transaction return freedom,
rotating class order, within-class ordinal order, ready-low no-mutation,
write fault, publication dependency, and descriptor-maintenance ready-low / a
single-fragment shared-R1 binding.  The cross-module binding is executed by
`kvpress/route_a_cross_closure_reference.py`.

The reference does not instantiate a controller queue, HBM port, macro, clock
cycle, physical FIFO, or a new scheduler.  The maintenance channel is a
logical ownership/transport class, not a physical second port, queue depth,
or service rate.
