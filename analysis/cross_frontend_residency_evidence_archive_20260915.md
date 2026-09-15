# Cross-frontend residency evidence archive — 2026-09-15

## Purpose and authority

This is a provenance index and claim-boundary archive for the completed
KVzap/Qwen3-8B, KVzap/Nous-Llama-3.1-8B-Instruct, SnapKV, and official trained
DMS studies. It does **not** replace an experiment manifest, frozen trace, or
freeze JSON; it selects no hardware parameter and is not an architecture
specification or RTL gate. Its purpose is to close the current evidence phase
without relabeling a frontend-specific realization as a universal mechanism.

The primary architecture path remains Route-A for stable KVzap retention:

```text
fine-grained stable retain decisions
  -> exact survivor packing
  -> bounded asynchronous admission
  -> hot / pending / packed attention-safe realization
```

The cross-model/frontend work asks where that path is portable and where its
specific realization ends. Evidence classes below remain literal:
**trace-derived**, **functional**, **modeled**, **measured Python-reference
software**, **unknown**, and **not applicable (N/A)** are never interchangeable.

## Completed anchor inventory

| Scope | Authoritative completed artifact | What it supports | What it does not support |
|---|---|---|---|
| KVzap + Qwen3-8B | `analysis/experiments/route_a4214_core_contract_closure_01/a4214_core_contract_closure_report.json` (SHA-256 `01434d764be9bb1cd7834bbb9c6ca511ae07dbeb393b0ea8837a8e50e8f59d9e`) | Qwen Route-A Core Contract v1 closure: original decision semantics, hot/pending/packed realization, same-mask attention reference, observed interface fields, and explicitly unselected modeled fields. | Hardware resource freeze, measured hardware benefit, universal workload distribution, or RTL. |
| KVzap + Qwen/Llama | `analysis/experiments/route_a_m6_cross_model_fixed_horizon_envelope_03/m6_cross_model_fixed_horizon_envelope_report.json` (SHA-256 `304fcbcb3290c833b2076a3b341a19328ef92ae7b68a1d3d8cf24dcbf0ad52d7`) | Two-model same-mask/lifecycle portability with separate fixed-row coverage descriptors. Qwen and Llama source/page/fan-in distributions remain separate. | A pooled resource distribution, common hardware dimension, or a transfer of Qwen A0--A3 numbers to Llama. |
| SnapKV + Qwen3-8B | `analysis/experiments/snapkv_route_a_p2_lifecycle_resource_descriptor_qwen3_8b_01/snapkv_p2_lifecycle_resource_descriptor.json` (SHA-256 `29835a960c9a010421bf088ad3a869c476f5c67041b0127e4395df41a7c1aa29`) | One terminal prefill action per identity, canonical original-position mapping, protected-suffix mapping, static packed terminal state, and prefill-tail same-mask functional probe. | Native SnapKV cache/decode semantics, generated-token actions, online maturity/pending, scheduler/backpressure, allocator, or hardware behavior. |
| Official DMS + Qwen3-8B | `analysis/experiments/dms_route_a_m4_active_resident_attention_qwen3_8b_retrieval_01/dms_m4_active_resident_attention_manifest.json` (SHA-256 `6e4dc1eda065f440800ee29c03f65ad59502cf95c84f2408dce7ce8e6485b028`) | Delayed eviction/reuse control replay; required native-slot order; and one-source active-resident decode attention replay over 144 calls without changing official execution. | Packed-cold mapping, source partition/merge, slot reordering invariance, capacity/traffic/timing, hardware, or RTL. |

## Corrected cross-frontend interpretation

### KVzap on two models: direct Route-A portability

The Qwen and Llama anchors support the same Route-A *semantic contract* on two
model/predictor/request sets. They do not say the two models have the same
retention distribution, source fan-in, tail behavior, layer count, or hardware
need. The valid conclusion is **two-anchor semantic portability with bounded
workload coverage**, not model-independent resource sizing.

### SnapKV: one-shot packed-residency evidence

SnapKV P0--P3/P2 establishes a terminal prefill decision stream and a bounded
canonical packed mapping. It is evidence for semantic--physical decoupling:
an irregular per-head retained prompt set can be represented in a regular
packed realization without changing the bounded same-mask prefill-tail probe.

It does **not** establish `SelectedPrompt U GeneratedKV` as an observed
descriptor: P3 executes zero generated-token forwards, and native SnapKV cache
replacement is deliberately unused. Generated-token behavior and decode
continuation are therefore **unknown/not observed**, not zero and not N/A.

### DMS: dynamic-resident boundary evidence

DMS emits delayed eviction controls and reuses native cache slots; an evicted
record disappears rather than becoming Route-A packed cold state. M3 records a
logical source-arrival serial per active slot, while M4 requires official native
logical-slot/block-table traversal for attention replay. In the accepted fixed
request, 269 of 288 final layer/KV-head states are nonmonotonic when native
physical-slot traversal is read by arrival serial.

Thus DMS supports a higher-level ordered active-resident-source interface, not
the claim that all frontends have hot/pending/packed cold lifecycle. The M3
serial is not a general captured original token-position field; any later
descriptor must keep **source arrival identity**, **logical-position
provenance**, and **required native traversal order** distinct.

## Commonality matrix at this archive point

`available` means bounded evidence exists in the named artifacts; it never
means the field is a universal hardware requirement.

| Descriptor field or mechanism | KVzap Qwen/Llama | SnapKV Qwen P0--P3/P2 | Official DMS Qwen M0--M4 | Archive classification |
|---|---|---|---|---|
| Layer, KV-head, query-to-KV group identity | available | available | available | Candidate semantic invariant |
| Attention epoch/phase | online lifecycle/decode events | `prefill_terminal` only | prefill plus fixed decode events | Candidate semantic invariant; granularity differs |
| Decision known/effective epoch | creation score and maturity effectivity | terminal only; online epoch unavailable | delayed decision and effectivity through ring reuse | Candidate semantic invariant, with optional values |
| Current visible resident set | hot + pending + packed exact mask realization | bounded terminal prefill-tail mapping only | active native resident slots at decode | Candidate semantic invariant |
| Identity/position provenance | original positions and append order | canonical original-position order | arrival serial observed; literal token-position capture not established | Common field is incomplete for DMS |
| Required traversal order | source/append-order contracts | canonical mapping for bounded probe | native slot/block-table order required | Candidate shared attention-interface field |
| Variable-length source state | available | static terminal source state | active resident slot length | Candidate shared primitive |
| Multi-source partial-softmax composition | functional Route-A mechanism | not established as native decode behavior | not applicable to accepted one-source M4 check | Optional composition, not universal |
| Pending FIFO/maturity service | Route-A-specific lifecycle state | unavailable, not zero | N/A | Persistent-packed realization extension |
| Append-only packed pages/page sealing | Route-A-specific realization | static mapping only | N/A | Persistent/one-shot packed extension, not invariant |
| Reclaim/reuse/free-slot control | N/A | N/A in evidence | available as DMS control/topology | Dynamic-resident-slot extension |
| Scheduler, source-ready/completion, backpressure | modeled/observed only on named KVzap studies | unavailable | unavailable | Unresolved; no cross-frontend conclusion |
| Capacity, traffic, latency, throughput, energy, area | only explicit KVzap models where named | unavailable | unavailable | Not a cross-frontend result |

## Archived decision

Do not add another pruning frontend or pursue a generic accelerator now. The
next task is a **Commonality Study**: determine which descriptor fields and
attention primitives are shared, while preserving realization-specific managers.
Its success condition is a precise boundary, not a predetermined unified
datapath. The plan is
`analysis/cross_frontend_commonality_study_plan.md`.

