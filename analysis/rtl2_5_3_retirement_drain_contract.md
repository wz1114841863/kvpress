# RTL2.5.3 — R6 retirement / drain fixed-membership closure

**Status:** `complete_directed_membership_and_bounded_fairness_evidence; r5_reclaim_order_pending`.

## Scope

RTL2.5.3 closes the already implemented R6 retirement collection protocol with
the real `route_a_component_status_collector` in a test-only composition.  It
does not change R6 state, drain membership, R5 reclaim ordering, scoreboard
events, source scheduling, or a controller/service-rate implementation.

The fixed global-drain membership is exactly these named facts:

| Collector source | R6 fact | Required phase |
|---|---|---|
| R1 | `r1_memory_drained` | pre-reclaim and final pass |
| R2 payload | `r2_payload_drained` | pre-reclaim |
| R2 descriptor | `r2_descriptor_drained` | pre-reclaim and final pass |
| R3 | `r3_m2_p3_drained` | pre-reclaim |
| R5 | `r5_page_manager_drained` | final global completion |
| S2/GQA | `s2_gqa_drained` | pre-reclaim |
| direct-pending | `direct_pending_drained` | pre-reclaim |
| R4 | `merge_drained` | pre-reclaim |

R1 remains ordered after both R2 partitions in the status collector.  Once
the pre-reclaim set is complete and R6 has no live control/merge/terminal
association, R6 may emit one matching R5 reclaim permit.  Acceptance of that
permit does not complete retirement: R5 must report its local completion, and
then R1/R2-descriptor must re-report the final pass because R5's descriptor
maintenance write invalidates their earlier drain facts.  `retire_ack` is
solely the final R6 output after all eight final requirements are true.

## Directed closure

`RouteARetirementDrainClosureSpec` provides two deterministic no-model
ChiselSim witnesses:

1. It withholds R4's drain fact, then shows that neither reclaim permit nor
   retire acknowledgement can appear.  After delivering the missing fact, it
   holds the permit ready-low, accepts it, confirms final-pass facts are
   blocked before R5 completion, withholds R5 drain, and finally accepts one
   stable matching `retire_ack` only after R5 plus final R1/R2-descriptor
   facts arrive.
2. It applies fixed-seed finite ready-low stalls to the reclaim permit and
   retirement acknowledgement.  Each carrier preserves its retirement
   identity while stalled; when the test environment eventually raises ready,
   the protocol completes.

The existing `RouteAFairReclaimIntegrationSpec` remains adjacent evidence that
the R1/R2/R5 reclaim transaction can perform its descriptor write/terminal
sequence under fixed-seed legal stalls.  It is not rewritten or treated as a
new physical-memory model.

## Assumptions and evidence boundary

The bounded-progress witness assumes that, after retirement stops new work:

- each named local owner eventually offers its asserted drain fact after its
  actual local predicate becomes true;
- R5 eventually completes the already-issued reclaim permit transaction; and
- the runtime eventually accepts the stable permit and `retire_ack` carriers.

The evidence establishes only that covered finite, fairness-constrained
interleavings completed without an observed protocol deadlock.  It is not a
formal liveness/deadlock-freedom proof and makes no latency, throughput,
controller, HBM, area, energy, PPA, model/GPU, numeric, or A4 DSE claim.

`descriptor_invalidate`, `page_free`, and `retire_ack` remain **declared-only
scoreboard targets** until RTL2.5.4 and RTL2.5.5 bind their owner-local
accepted carriers.  This test observes the existing R6 hardware carrier only;
it does not emit or infer a scoreboard event.
