# RTL2.1c — atomic publication and authority handoff

**Status:** implementation and directed functional closure complete.

RTL2.1c activates the already-frozen atomic publication boundary; it does not
revisit admission, pruning, pages, M2 organization, queues, scheduling, S2,
direct-pending, R4 numeric behavior, physical memory, timing, or PPA.

```text
R3 complete P3 write + R5 descriptor prerequisite
  -> R3-owned exact M2 member request (member 0, then member 1)
  -> replaceable M2 reference protocol completion
  -> R3-owned publication candidate
  -> exact publication request return
  -> R3 -> R5 nested visibility apply/ack
  -> metadata_publish_commit / pending -> packed observation
```

## Owner and implementation boundary

`RouteAM2P3Wrapper` (R3) is the sole issuer of the two frozen semantic M2
member coordinates and of the publication candidate.  It holds one exact
outstanding member identity `(layer, stage_generation, tag, member)` and one
exact outstanding publication identity `(layer, stage_generation, tag)`.
Only a matching returned carrier may advance either state.

`RouteAM2ReferenceProtocolProvider` is a replaceable functional protocol
endpoint used by the production composition.  It may only reflect a carrier
already issued by R3 and returns an OK member result; it cannot create a layer,
generation, tag, membership, descriptor fact, or authority transition.  It is
not an M2 SRAM macro, port-count choice, coherence protocol, controller,
latency/service model, or PPA evidence.  Tests bypass it solely to inject
negative terminals.

R5 remains the only owner of page-list visibility.  R3 cannot produce
`metadata_publish_commit`, post-commit member observations, or the exact
`pending -> packed` authority transition until R5 has accepted and returned
the matching nested visibility acknowledgement.

## Fail-closed rules

- A response without the exact outstanding member identity is `ready=0` and
  cannot change M2-member state, P3 state, visibility, or authority. An
  unmatched R1 external response is instead consumed at R1's stale-response
  boundary, but cannot become a core response or mutate the write association.
- A publication request is `ready=0` until R3's exact candidate has been
  accepted; stale/mismatched layer, generation, or tag is `ready=0`.
- A matching member fault, descriptor terminal fault, or rejected nested
  publication acknowledgement makes the affected stage `FAULTED`; it cannot
  issue another member, candidate, commit, or authority handoff.
- `page_write_commit`/payload durability and descriptor durability remain
  private.  Neither is packed authority or readable visibility.
- After a successful commit, post-commit observations drain before that P3
  layer can be claimed again.  This is an existing ownership/reuse dependency,
  not a cycle or bandwidth claim.

## Directed verification

`RouteA2_1cAtomicPublicationHarnessSpec` contains no model/GPU execution. It
uses the actual R3 -> R2 -> R1 -> R5 write path and exposes only M2 return
carriers for deterministic negative injection.

1. Two sequential one-record pages execute eight 64-B payload fragments plus
   sidecar each. The first page publishes through two exact member completions
   and R5 nested acknowledgement; the second page then executes both new-page
   and tail-link descriptor writes.
2. A stale R1 response incarnation is consumed without changing the
   `WRITE_ISSUED` association; stale old-member and generation-mismatched
   publication carriers are held fail-closed before a matching carrier is
   accepted.
3. An R1 descriptor terminal fault and an exact outstanding M2 member fault
   each leave the stage `FAULTED`, with no M2 publication candidate or
   authority handoff.

This is pure functional transaction evidence. It makes no RTL signoff,
formal-proof, deadlock-freedom, numerical-correctness, timing, throughput,
energy, area, HBM-controller, or PPA claim.
