# RTL3.5-B — functional attention-partial provider

**Status:** `implemented_pure_software_functional_partial_provider_pre_numeric_rtl`.

RTL3.5-B implements the uniquely named provider frozen by RTL3.5-A as a
pure-software, stateless functional PE/reference model:

```text
accepted frontend query context + accepted source-owner K/V/position lease
  -> route_a_functional_attention_partial_provider
  -> existing SourceServicePartialOffer + eight SourceServiceValueFragments
  -> existing source packet adapter / R4 structural acceptance
  -> existing RTL3.4-B functional R4 merge provider
```

The model is `kvpress/rtl3_5b_functional_attention_partial_provider.py`.  It
is not Chisel RTL and is not bound into `route_a_kv_subsystem_top`.  Existing
testbench packet ingress remains a separate structural fixture until a later
reviewed cross-language binding; this phase does not bypass Chisel packet
acceptance.

## Exact functional input and owner rules

The provider accepts only the RTL3.5-A association:

- `FunctionalAttentionQuery` is the common-front-end-owned, finite 128-lane,
  already-RoPE-applied query for one exact `(identity, layer, kv_head,
  consumer_id, query_head, query_position)`.
- The Qwen anchor requires `query_head = 4 * kv_head + consumer_id`, with
  36 layers, 8 KV heads, and four consumers.  It deliberately does not create
  a portable query-head mapping in hardware.
- `FunctionalSourceLease` is one source-owner fact (`hot`, `pending`, or
  `packed`) with immutable source instance coordinate/generation and a nonempty
  increasing logical-position sequence of finite 128-lane K/V records.
- Both query and source K use
  `qwen3_rope_applied_at_q_and_k_creation_v1`: query RoPE is supplied by the
  frontend, and K was rotated at KV creation.  The provider never applies or
  re-applies RoPE.
- The provider checks exact identity/layer/KV-head matching and causal
  visibility before producing any packet.  Rejected associations emit no
  offer, fragment, consumer commit, source release, authority transition, or
  Full-KV fallback.

The source owner remains a K/V/position/source-instance owner only.  R6 still
owns source-plan acceptance, R4 still owns structural packet acceptance and
consumer commit, source owners still own four-consumer release, and R6 still
owns the group terminal.  The functional provider owns no schedule, buffer,
credit, authority, result, or terminal state.

## Functional result representation

For one accepted source lease, the provider evaluates the Qwen-anchor causal
scaled dot-product partial with semantic scale `1 / sqrt(128)`:

```text
logit_i = dot(Q_already_rope, K_i_already_rope) / sqrt(128)
m       = max_i(logit_i)
l       = sum_i(exp(logit_i - m))
o       = sum_i(exp(logit_i - m) * V_i)
```

It then uses the pre-existing `MergePartial.present` / `MergePacket.from_partial`
reference to make the externally observable `(m, l, o)` binary32 packet.  The
result is exactly one *present* header and eight ordered 64-B value fragments,
with the frozen source ordinal, source instance, and consumer ID.  The helper
`as_r4_accepted_packet()` is only a reference-test conversion into the
RTL3.4-B provider; it neither substitutes for nor bypasses the Chisel
ready/valid acceptance boundary.

The host `exp` and host precision are reference computation only.  This phase
does not claim bit-equivalence to a future numerical RTL, select an exp
approximation/internal precision, or authorize a floating-point datapath.

## Tests and fail-closed coverage

The directed no-model tests cover all three source ordinals, exact eight
fragment packet shape, scaled-partial reference arithmetic, the Qwen four-head
mapping, identity mismatch, causal-position violation, unordered sidecar
position rejection, and three-source handoff into the existing RTL3.4-B merge
provider.  They establish neither Chisel integration nor full attention RTL
correctness.

## Exclusions and next boundary

RTL3.5-B selects no Chisel attention MAC/RoPE/exp/FP implementation, query or
K/V physical transport, payload storage, source scheduler, source reorder,
controller, SRAM/HBM macro, clocking, latency, throughput, area, energy, PPA,
model/GPU result, or A4 DSE.  It does not alter pruning, admission,
publication, one-authority residency, GQA legality, source-release, or R4/R6
terminal semantics.

The next required scope is a separate reviewed binding from this functional
provider's packet outputs to the existing Chisel source-packet adapter.  That
binding must prove exact cross-language packet/identity association and retain
the existing R4 structural acceptance; it may not activate a production top.

## No-model validation

```bash
.venv/bin/python -m pytest -q \
  tests/test_route_a_merge_numeric_reference.py \
  tests/test_rtl3_4b_functional_r4_provider.py \
  tests/test_rtl3_5b_functional_attention_partial_provider.py \
  tests/test_rtl3_5b_functional_attention_partial_provider_manifest.py
.venv/bin/python tools/validate_rtl3_5b_functional_attention_partial_provider.py
```

Exact source/hash binding is in
[`rtl3_5b_functional_attention_partial_provider_manifest.json`](rtl3_5b_functional_attention_partial_provider_manifest.json).
