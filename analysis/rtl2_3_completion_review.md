# RTL2.3 completion / cross-owner integration review

**Review status:** `partial_pass_for_ingress_endpoints_and_structural_r4_packet_ingress_only`.

**Active navigation:** [`RTL2.3-R`](rtl2_3_reconciliation_01.md) reconciles
future phase/event labels without changing this partial disposition or
activating an event.

This review checks the completed RTL2.3.0--RTL2.3.3 slices against the phase
contract, rather than treating individually passing isolated tests as a full
source-service completion.  It uses architecture and Chisel source inspection
plus the recorded no-model directed tests.  It makes no performance, numeric,
physical-memory, controller, timing, PPA, or end-to-end RTL correctness claim.

## Closed preparation scope

| Required preparation boundary | Evidence | Review disposition |
|---|---|---|
| Immutable pre-R1 read facts cannot be response-derived. | RTL2.3.0 descriptor carries handle, valid count, generation, endpoint, fragment count and descriptor. | closed |
| A named producer can form only a legal read `SourceCandidate`. | RTL2.3.1 state-free adapter copies ordinal/ID/predicate and fails closed on malformed input. | closed in isolation |
| Route-A incremental R3/R5 lanes can obtain immutable registry associations before pre-R2 composition. | RTL2.3.2 isolated bridge + registry + merge handles pack-read, direct-pending, packed-S2. | closed in isolation |
| Top does not become a read/write arbiter. | RTL2.3.3 places dual-ingress choice in R2 and ties the top read carrier inactive. | closed |
| Existing R2 rotation/issue ownership is retained. | No R2 selection logic was moved; focused test shows R2-only input acceptance and ready-low hold. | closed at ingress boundary |
| Read/write producers share exactly one registry allocation owner. | RTL2.3-C1 six-lane bridge replaces the production write-only bridge and rejects lane/class mismatch. | closed |
| Non-top R6 source-plan producer is explicit. | C6 `route_a_source_plan_binder` validates and holds an upstream declared nonempty canonical plan before R6 intake. | closed; no source service activated |
| R6 accepted-plan copy and exact owner availability reach the packet adapter. | C7 adds `route_a_source_service_packet_adapter` to the composition top and uses owner-local hot/direct/S2 observations. | closed; source packet ingress remains fail-closed |

## Unclosed phase requirements

The RTL2.3 phase heading requires a **functional source packet/fragment path**
and source completion association.  That outcome is not yet present.  The
following are real blockers, not harmless documentation gaps:

| Missing closure | Why it blocks RTL2.3 completion |
|---|---|
| Live R3/R5 read-issue producer attachment. | C2/C3 attach explicit R3 pack/direct work and C4 attaches explicit packed-S2 work through actual C1/R2/R1 chains in integration harnesses, but the production top still has no authorized live work producer. |
| Exact R1 read response to P3/S2/direct endpoint adapters. | C2 closes P3, C3 closes direct-pending, and C4 closes packed-S2 in integration harnesses, including stale/mismatch/fault fail-closed handling. The production typed read carrier remains inactive. |
| P3 pack-read source completion and sidecar association. | C2 proves one eight-fragment retained-member transaction reaches P3 `COMPLETE` only with existing sidecar binding, but does not activate top source service or source completion. |
| S2 packed-fill open/payload/sidecar/terminal sequence. | C4 proves the exact sequence in an integration harness, including a full 64-record/512-fragment page and sidecar gate; it does not attach an authorized live top producer or source-service egress. |
| Direct-pending terminal sequence. | C3 passes eight transient record fragments through the typed endpoint and emits the existing terminal only after the eighth accepted fragment. It is not yet a top-level source packet path. |
| Source packet emission to R4 and four-consumer completion/release wiring. | **Partially closed by C5:** an R6 accepted plan copy and owner-provided structural packets reach the existing R4 parser for every present-source/four-consumer combination. Still unclosed: real hot/direct/S2 partial producers, owner-side commit consumption/release, R6 merge request, and terminal association. |

## Review disposition and remaining closure order

RTL2.3 is **not complete**.  The code is ready for the next narrow closure,
but it must not be represented as a production source-service dataflow.

1. **C6 is complete:** the non-top source-plan binder now supplies the only
   R6 plan producer; C5 still cannot synthesize a plan.
2. **C7 is complete:** the existing adapter now receives the accepted plan copy
   plus exact owner availability observations in the composition-only top.
3. **C8** proves all seven masks through four commits, one exact owner release
   per present source, and the R6 merge request; it must not treat C5's
   verification offers as source arithmetic.
4. **C9** replaces the isolated C2/C3/C4 endpoint witnesses with one authorized
   top composition path before an RTL2.3 completion review.

The review permits this next control/dataflow closure only.  It does not
authorize changing pruning, admission, page size, M2/P3 organization, S2
count, GQA legality, scheduler, atomic publication, numeric merge, physical
HBM/SRAM/controller, profiling, timing, or PPA work.
