# Cross-frontend Commonality Study plan — C0–C5

## Scope

This plan follows `cross_frontend_residency_evidence_archive_20260915.md`. It
does not reopen Qwen A4.2, rerun completed semantic gates, select hardware
parameters, or enter RTL. Route-A persistent-packed KVzap remains the primary
architecture path. SnapKV and DMS are bounded contrast cases used to identify
the portability boundary of its mechanisms.

The central question is:

> Which part of semantic-preserving, fine-grained KV realization is common
> across qualitatively different pruning frontends, and which part must remain
> a realization-specific manager?

## Descriptor v1

`CrossFrontendResidencyDescriptor v1` is a schema specification, not a cache
format and not a hardware interface. Every value must carry one of
`observed`, `derived`, `modeled`, `unknown`, or `not_applicable`; `unknown` is
not encoded as zero.

### Core semantic fields

| Field | Meaning | Required handling |
|---|---|---|
| `model_topology` | model ID/revision, layer count, KV-head count, query-to-KV group relation | Model-level, never pooled into accelerator dimensions. |
| `identity` | `(layer, kv_head, source_record_id)` | `source_record_id` may be a canonical position or an arrival serial; label which. |
| `epoch` | phase, event kind, forward/decode index, `q_len` | `prefill_terminal` is valid; it does not imply token-level timeline. |
| `decision` | value, known epoch, effective epoch | Missing timing remains unknown; frontend may expose no decision. |
| `visibility` | whether a record must be attention-visible at the epoch | Separate from whether a physical realization has completed. |
| `position_provenance` | original logical position if captured, otherwise explicit serial/unknown | Never infer literal token positions from DMS slot IDs. |
| `traversal_order` | required source traversal order and its reason | DMS native slot order is distinct from source arrival serial. |
| `attention_binding` | query/KV grouping and applicable semantic comparator | Preserve frontend-specific comparator. |

### Realization extensions

| Extension | Applies to | Extension-only fields |
|---|---|---|
| `persistent_packed` | KVzap Route-A | hot/pending/packed state, maturity, admission service, append-only pages, page sealing/tail. |
| `one_shot_packed` | SnapKV P0--P3 mapping | terminal action, protected observation suffix, canonical static packed state, initial compaction. Generated decode state is currently unknown. |
| `dynamic_resident_slot` | official DMS M0--M4 | active slot, delayed eviction, reclaim/reuse, slot-to-arrival identity, required native traversal order. |

No extension field may be promoted to core merely because it is convenient for a
single frontend. In particular, pending, page descriptor, free-slot list, and
native cache block table are not v1 core fields.

## Comparator discipline

Commonality does not require one shared oracle. C4 must retain the comparator
already validated for each frontend:

| Frontend | Existing bounded comparator |
|---|---|
| KVzap | online same-mask dense versus Route-A, with Full-KV bypass retained as distinct control |
| SnapKV | same-mask prefill-tail probe; no native SnapKV decode claim |
| DMS | unchanged official native DMS FlashAttention output versus one-source active-resident FP32 replay |

## Stages and gates

| Stage | Inputs | New output | Pass/fail gate | Claim boundary |
|---|---|---|---|---|
| C0 — evidence freeze | Existing completed manifests named in the archive | Hash-bound `cross_frontend_c0_evidence_index` report | Every source exists, has expected schema/status/hash; no raw trace copied or changed | Provenance index only. |
| C1 — semantic descriptor | C0 index plus existing manifest fields | Versioned descriptor specification and field-availability matrix | Every field is typed and every unavailable field is `unknown` or `not_applicable` with reason | No model run; no common hardware interface. |
| C2 — realization adapters | C1 plus KVzap/SnapKV/DMS artifacts | Three per-frontend descriptor projections | Projection preserves source provenance/order and rejects fabricated fields | Mapping/classification only; no allocator or physical-capacity claim. |
| C3 — commonality analysis | C2 projections | Hash-bound invariant/specific/unresolved matrix | No field is marked invariant unless available in all three projections; differences remain explicit | Candidate common primitives only. |
| C4 — attention primitive study | C3 plus existing frontend comparators | Per-frontend, semantics-checked source-traversal reports and comparison summary | Each uses its own accepted comparator; no mandatory multi-source requirement; failure may narrow commonality | Determines whether a useful common source-traversal primitive exists, not hardware performance. |
| C5 — hardware direction decision | C0–C4 archive | Decision memo: Route-A persistent-packed focus vs candidate common substrate | Evidence, not preference, determines branch; all unresolved resource fields remain listed | No RTL or parameter freeze unless a separate later gate authorizes it. |

## C1 implementation and interpretation

`tools/build_cross_frontend_c1_semantic_descriptor.py` consumes the completed
C0 evidence index and the same four JSON inputs. It rechecks each C0-bound
SHA-256/schema/status and, by default, its literal path before writing a new
`cross-frontend-c1-semantic-descriptor-1.0` report. The report types every
core field at `(model, layer, kv_head, epoch)` grain and records availability
separately for KVzap persistent-packed, SnapKV one-shot packed, and official
DMS dynamic-resident-slot evidence.

C1 is an inventory of what can be stated truthfully, not a claim that the
three frontends have one cache format. `pending`, page descriptors, free-slot
lists, and DMS native block tables remain realization extensions. Every
`unknown` or `not_applicable` entry requires a reason: in particular, SnapKV
generated decode remains `unknown`, and DMS literal original position remains
`unknown` even though its arrival serial and native traversal order are
observed. No model is run and no common hardware interface, resource envelope,
parameter, or RTL choice is produced.

For cross-host reproduction, an explicit hash-preserving relocation may use a
fresh staging path only when the manifest SHA-256 still equals the C0-bound
value; the C0 origin path and actual staging path are both recorded. It never
authorizes overwriting an existing experiment output.

The accepted C1 output is
`analysis/experiments/cross_frontend_c1_semantic_descriptor_01/cross_frontend_c1_semantic_descriptor_report.json`
(SHA-256 `7b37e8f0945018f6b387085ea129f10758962dd987b4d8437cb243c7a45677a7`).
It reverified all C0-bound sources, typed all eight core fields for every
frontend, and selected no hardware interface or parameter.

## Minimal missing fields and collection policy

1. **DMS position provenance:** M3 has source arrival serials and native order,
   not a generally captured original token-position field. Collect a compact
   position/serial relation only if C1 cannot represent the required order
   truthfully.
2. **SnapKV decode behavior:** generated-token decisions/cache semantics are
   unobserved. Do not collect them merely to fill a table; collect only if C4
   needs a decode-source claim. Otherwise retain `unknown`.
3. **Source decomposition:** KVzap has functional multi-source composition;
   SnapKV and DMS do not need artificial sources. C4 must permit a single
   source and make optional composition conditional on a realization actually
   having distinct physical sources.
4. **Temporal scheduler fields:** source-ready/completion ordering,
   backpressure, and queue state are not common evidence today. They are out of
   C1–C4 unless a later architecture branch explicitly needs them.

Any new collector must be read-only, default-off, preserve its frontend's
native/model result under trace-off/on comparison, support `--help`, use a new
output directory, and record provenance. No Python runtime, profiler,
allocator, or prior byte/cycle proxy may be renamed as HBM traffic or hardware
performance.

## C5 decision criteria

Choose **Route-A persistent-packed backend** if C3/C4 finds that the only
strongly shared primitive is generic attention traversal while KVzap's
asynchronous admission and packed lifecycle remain the architectural source of
value. Choose **candidate common variable-length source substrate plus
realization managers** only if all three frontend projections preserve the same
well-defined source traversal/visibility contract and C4 supports it without
frontend-specific semantic loss. Neither outcome is a failure.

## Final classification matrix to preserve

| Invariant candidates | Realization-specific mechanisms | Unresolved |
|---|---|---|
| layer/KV-head identity; query-to-KV mapping; epoch; visibility; explicit provenance/order; variable-length active source traversal | KVzap pending/admission/page sealing; SnapKV terminal compaction/protected suffix; DMS delayed eviction/reuse/native slot order | Literal DMS token-position provenance; SnapKV decode behavior; value of optional multi-source composition outside KVzap; scheduler/backpressure; resource envelope and hardware direction |
