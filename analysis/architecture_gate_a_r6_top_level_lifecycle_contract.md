# Gate-A R6 — generic lifecycle adapter and top-level graph closure

## Status and boundary

**Status:** `complete_pure_software_top_level_lifecycle_contract; pre_rtl_only`.

R6 closes the top-level producer/consumer graph and the finite generic
lifecycle adapter for the Qwen3-8B Route-A anchor. It does not expose KVzap
score, threshold, predictor type, weights, or decision logit to the KV
subsystem. The frontend supplies immutable post-decision retention events only.
R6 is not predictor integration, model/GPU execution, a new A4 DSE, a
controller/FSM implementation, timing, throughput, energy/PPA, or RTL evidence.

## Top-level ownership graph

```text
frontend lifecycle adapter
  session_start / kv_arrival / maturity_disposition / attention_request / retire
                 |
                 v
        generic lifecycle controller ------------------+--------------------+
          | hot / retain / drop                        |                    |
          v                                            v                    v
    common hot-source path                    R3 M2/P3 + R5 page manager  runtime-retire
          |                                      |             |             adapter
          |                                      +--> descriptor maintenance --+
          +----> common S2/GQA source wrapper <- R2 -> R1 core_mem_if_v1 <---+
                         |                    ^
                         v                    |
                  R4 numeric merge wrapper <--+-- Gate-A1 direct-pending endpoint
                         |
                         v
                 attention terminal / fault status
```

Common infrastructure is the R1/R2 core-side memory wrapper and the two S2
slots with four-consumer GQA fanout. Route-A increments are lifecycle control,
the Gate-A1 direct endpoint, R3 M2/P3, R5 page management, and R4 numeric
merge. Runtime retirement is an integration boundary. The graph declares
ownership/dependency only; it selects no physical modules, queues, ports,
controllers, or overlap schedule.

## Generic frontend boundary

All frontend events are decoupled `valid/ready` events in `core_clk`; payload
is stable until accepted. Ready-low may delay only. It cannot change a mask,
disposition, source set, FIFO order, ownership, admission, or terminal result.
No rate, cycle count, or controller service guarantee is implied.

| Event | Finite payload | Producer -> consumer |
|---|---|---|
| `session_start_req` | `session_id[0]=0`, `context_tokens=32768` | frontend -> lifecycle adapter |
| `kv_arrival_req` | `entry_id[23:0]`, `layer[5:0]`, `kv_head[2:0]`, `logical_position[14:0]`, opaque `payload_ref[63:0]` | frontend -> lifecycle controller |
| `maturity_disposition_req` | `entry_id[23:0]`, `disposition[0]` `{DROP, RETAIN}` | frontend -> lifecycle controller |
| `attention_service_req` | `(rid[2:0], incarnation[1:0])`, `layer[5:0]`, `kv_head[2:0]`, `query_position[14:0]` | frontend -> source service |
| `session_retire_req` | `session_id[0]=0`, `(rid[2:0], incarnation[1:0])` | runtime -> runtime-retire adapter |

`payload_ref` is an opaque logical frontend handle, not a physical HBM address
or an R1-address replacement. The widths, `entry_id` derivation, and 128-token
hot boundary below are the Qwen Route-A **anchor profile**, not predictor
fields or a cross-algorithm protocol choice. Arrival is exactly once and
monotonic per layer/KV-head stream, with
`entry_id=((logical_position*36)+layer)*8+kv_head`. Maturity is exactly once
after the 128-token hot boundary; its disposition is immutable. The adapter
has no score/threshold/predictor field.

The output attention dispatch bitmap is `{hot[0], pending[1], packed[2]}` in
canonical order and has no Full-KV bit. Terminal attention status is exactly
one `ok/fault` result per accepted identity. Matching retire identity returns
only through `session_retire_ack`. These are logical handshakes, not selected
wires or a controller protocol.

## Lifecycle, source, reset, and retirement dependencies

Arrival creates hot ownership. DROP removes retained ownership; RETAIN moves
hot to pending exactly once. Only the existing R3 payload-durable/private-M2
group `metadata_publish_commit` action transfers pending to packed. The adapter does
not publish metadata or manufacture a fallback source.

An attention request discovers causal hot, pending, and packed sources in the
frozen order. Packed uses R2 publication eligibility and common S2/GQA;
pending uses only Gate-A1 direct delivery; hot uses the hot path. Source release
still requires all four consumer updates. R4 consumes only after those updates
commit; its `numeric_fault` is consumed as the exactly-one outward attention
terminal fault, with no retry, Full-KV fallback, mask/admission change, or
early source release. No path may retry, substitute
Full-KV, drop/reorder work, or alter mask/admission semantics.

After destructive reset, `session_start_req` waits for `mem_init_done`,
`m2_p3_init_done`, and `page_manager_init_done`. S2/direct/merge local
associations reset in `core_clk`; R1 still requires external suppression of
pre-reset responses. Reset does not erase HBM or relax authority/generation.

Retire stops new arrival/maturity/attention acceptance. Existing attention can
reach its single terminal result. Matching `session_retire_ack` waits for the
single global predicate: R1 live transactions; R2 payload-arbiter and
descriptor-maintenance grants; R3 M2/P3 groups/stages; R5 page/descriptor
operations; S2/GQA ownership; direct-pending ownership; and R4 merge state
are all drained. R5 then owns its already-frozen per-page
quiescence/invalidation/generation reclaim. This is an event dependency, not a
timeout, latency, or controller schedule. A retired anchor session cannot
start another session until destructive reset and the complete init
acknowledgement sequence reestablish its local namespaces.

Fault is fail-closed and reports upward. Detailed fault wires, ECC, retry,
timeout, logging, and recovery remain unselected; Full-KV is never a fallback.

## Executable evidence boundary

`kvpress/route_a_lifecycle_adapter_reference.py` and
`tests/test_route_a_lifecycle_adapter_reference.py` are pure-software
architecture-contract evidence. They check finite generic ports,
predictor-field exclusion, immutable disposition, authority path, canonical
source membership, identity lifetime, reset/init, and retire/drain ordering.
They make no model/GPU, timing/throughput, controller, HBM, PPA, RTL,
accuracy, or new-A4-DSE claim.
