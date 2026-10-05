# RTL2.3 completion / cross-owner integration review

**Review status:** `pass_for_control_protocol_complete`.

**Active navigation:** [`RTL2.3-R`](rtl2_3_reconciliation_01.md) reconciles
future phase/event labels without activating a host-side event.

This review checks the completed RTL2.3.0--RTL2.3.3 and C1--C9 slices against
the phase contract, rather than treating individually passing isolated tests
as production source-service completion. It uses architecture and Chisel
source inspection plus recorded no-model directed tests. It makes no
performance, numeric, physical-memory, controller, timing, PPA, or end-to-end
RTL correctness claim.

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
| Four R4 commits produce one exact owner release and then one R6 merge request. | C8 names the R4-to-owner commit router and directed integration exercises all seven nonempty source masks. | closed in verification-packet harness; opaque packets remain non-numeric |
| C2/C3/C4 endpoint routing is uniquely composed at top. | C9 adds `route_a_read_endpoint_demultiplexer`, binds all three existing endpoint modules, and uses explicit mutually-exclusive verification ingress. | closed; C4's 10/9 logical carrier bound is covered by init/drain regression |

## Completion disposition and deferred realization

The C2/C3/C4 endpoint attachment blocker is closed. The C6--C9 evidence is
sufficient for the narrow `control_protocol_complete` disposition: every
control association required for the planned nonnumeric packet protocol has a
named owner and directed coverage. This is not a production source-service or
numeric-dataflow completion. The following are explicitly deferred
realization boundaries, not RTL2.3 blockers:

| Deferred item | Boundary retained after this review |
|---|---|
| Verification ingress replacement. | C9 intentionally keeps named verification-environment work/open ingress until a separately authorized production producer realization; it is not an implicit scheduler or source-plan owner. |
| Numeric source partial production. | C5/C7 packets remain structural verification packets. No hot/direct/S2 payload-to-partial arithmetic or production packet producer is claimed. |
| R4 result/fault terminal. | RTL2.4 alone may activate the replaceable deterministic result/fault stub; no exp/FP/online-merge implementation is selected. |
| Production source-service scheduling. | C2's one-member work carrier and C3/C4 environment work do not choose cross-member issue order, outstanding count, response reordering, or service rate. |
| Physical realization. | The C4 top elaboration bound is logical count/index capacity only; SRAM/HBM/controller/clock/overlap/PPA remain open. |

## Closure evidence and next entry

RTL2.3 is complete only in this control-protocol sense; it must not be
represented as a production source-service dataflow.

1. **C6 is complete:** the non-top source-plan binder now supplies the only
   R6 plan producer; C5 still cannot synthesize a plan.
2. **C7 is complete:** the existing adapter now receives the accepted plan copy
   plus exact owner availability observations in the composition-only top.
3. **C8 is complete:** all seven masks now traverse four commits, one exact
   owner release per present source, and the R6 merge request without treating
   C5 verification offers as source arithmetic.
4. **C9 is complete:** the isolated C2/C3/C4 endpoint witnesses now share the
   authorized descriptor-selected top composition path. The top's C4 presence
   requires the logical 10-bit count / 9-bit index carrier bounds; the init/
   drain harness ties all C9 verification ingress inactive and passes again.

The review permits entry to RTL2.4's result/fault-stub closure only. It does not
authorize changing pruning, admission, page size, M2/P3 organization, S2
count, GQA legality, scheduler, atomic publication, numeric merge, physical
HBM/SRAM/controller, profiling, timing, or PPA work.
