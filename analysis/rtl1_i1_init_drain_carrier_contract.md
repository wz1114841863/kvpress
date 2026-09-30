# RTL1-I1.0 — init/drain carrier and hierarchy amendment contract

**Status:** `complete_carrier_only; top_behavior_still_inert`.

This contract is the first, deliberately non-behavioral half of RTL1-I1. It
authorizes the carrier required to compose R1 reset initialization and the
named R6 drain facts. It neither changes a frozen owner nor makes the top
functional. In particular, it does not choose an HBM/controller reset
sequence, CDC, physical FIFO depth, clock/timing target, PPA model, source
delivery path, publication association, R4 numeric realization, or new A4
DSE.

## Dedicated external initialization acknowledgement

`external_core_mem_if_v1.init_ack` is a decoupled adapter-to-R1 carrier whose
sole payload is `adapter_epoch_ready`. It is the only permitted external
initialization acknowledgement. It is intentionally separate from
`external_core_mem_if_v1.response`; an ordinary R1 response, including a
fault/terminal response, is never an init fact.

The external adapter may assert `adapter_epoch_ready` only after it has
suppressed or drained pre-reset responses for its current reset epoch. R1 will
not convert this carrier into traffic acceptance until RTL1-I1 behavior. The
acknowledgement gives no native HBM controller, PHY, or CDC semantics.

## Status-collection amendment

RTL1-I1 adds one integration-only child, `route_a_component_status_collector`,
under `route_a_kv_subsystem_top`. This is the hierarchy amendment anticipated
by RTL1-I0. It owns no token/page/source/transaction authority and holds no
architectural resource table. Its sole permitted state in the behavioral step
is a ready/valid staging register plus a delivered-drain bitmap needed to
avoid duplicate delivery to R6 during a retirement epoch. Those are protocol
serialization state, not a selected physical FIFO depth or a new queue
contract.

Its eight owner-local sources are frozen as follows:

| Source | Named fact(s) | Local predicate authority |
|---|---|---|
| R1 | `mem_init_done`, `r1_memory_drained` | R1 init epoch; no R1 live read/write identity |
| R2 | `r2_payload_drained`, `r2_descriptor_drained` | R2 slot/outstanding state partitioned by frozen class |
| R3/M2/P3 | `m2_p3_init_done`, `r3_m2_p3_drained` | initialized, no live P3/group/publication control |
| R5 | `page_manager_init_done`, `r5_page_manager_drained` | initialized, no allocation/build/visibility control still live |
| S2 | `s2_gqa_drained` | both S2 slots empty |
| direct | `direct_pending_drained` | endpoint inactive |
| R4 boundary | `merge_drained` | no packet, commit, merge, or terminal state |

R6 remains the only lifecycle/session-start/retire-ack owner. The collector
may serialize, stall, and replay an unaccepted owner fact, but may not
fabricate, merge, drop, or change a fact. It may offer drain facts only while
R6 declares retirement collection active; it must retain an accepted fact
stable while R6 ready is low.

## I1.0 implementation disposition

The Chisel bundle now carries `init_ack`, and the top's external port exposes
it. R1 deliberately ties the acknowledgement not-ready in this carrier-only
commit and retains its pre-existing local `mem_init_done` test input. No status
producer/collector/top wiring is active yet. RTL1-I1 behavior must replace
that local test gate with the dedicated external handshake and bind all eight
local predicates without changing R1 traffic semantics.

This is no-model, no-GPU, no-cycle/timing/throughput, no-PPA, and no-RTL
correctness evidence. It is an interface closure only.
