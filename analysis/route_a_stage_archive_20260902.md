# Route-A staged evidence archive — 2026-09-02

## Purpose and authority

This is a **status archive**, not an architecture-specification freeze and not
a replacement for any frozen trace or experiment manifest.  It consolidates
the Route-A0 through Route-A3.19 evidence produced from the official Qwen3-8B
KVzap front end (threshold `-4`, hot window `128`) and points to the original,
provenance-bearing artifacts.  All byte, cycle, utilization, and break-even
numbers below remain explicit models unless an artifact says otherwise.

The controlling documents remain `AGENTS.md`, `RESEARCH_CONTEXT.md`,
`TRACE_SCHEMA.md`, `KVZAP_ARCHITECTURE_PATH.md`, and
`analysis/route_a_research_plan.md`.  No frozen predictor-only trace, A2
lifecycle trace, or earlier experiment result was edited to make this archive.

## Research question and design under test

Route A keeps KVzap's original per-`(layer, kv_head)` token mask.  It uses:

```text
predict once -> regular 128-token hot window -> maturity decision
             -> drop OR append kept K/V into packed cold pages
             -> repeated cold-KV reads through a load-aware backend
```

The question is not whether logical pruning alone creates speedup.  It is
whether one-time admission and packing can be amortized by later sparse
attention reads, while preserving KVzap's mask semantics and managing
variable-length head/page work.

## Evidence ledger

| Stage | Question answered | Principal result | Evidence level / boundary |
|---|---|---|---|
| A0 | Can the original mask become compact physical capacity? | Per-head append-only packed pages at `P={16,32,64,128}` retain nearly all of the logical capacity advantage; tail/metadata costs are explicitly bounded. | Static replay of frozen predictor-only masks.  Not admission, allocator, HBM, latency, or throughput. |
| A1 | Does variable-length work require a scheduler? | Static head ownership exposes imbalance; length-aware/page scheduling supplies the workload and overhead terms for later DSE. | Offline simulated batches, not serving execution. |
| A2 | Is a decode-lifecycle input available without perturbing generation? | Three-pass, read-only collector validates normal/silent/recorded answer and lifecycle-digest equivalence; it records maturity/admission inputs and observed horizons. | Dense Full-KV generation stays authoritative; it is not policy-on sparse attention.  See `analysis/route_a2_lifecycle_freeze.json`. |
| A3.5--A3.11 | Can branch-consistent admission, pending FIFO, pages, banks, staging, and merge costs be made explicit? | Shadow/replay and memory-system DSE make continuous bounded admission, dual-store pending reads, page/bank layout, staging fallback, and scheduler costs auditable. | Trace-derived state plus modeled bytes/cycles; no actual HBM/allocator/latency result. |
| A3.12--A3.15 | Is a caller `max_new_tokens` cap sufficient to protect short requests? | No.  A high-cap Qasper request naturally stopped after 17 calls; a cap is an upper bound, not a continuation guarantee. | Validated lifecycle counterexample; not a general predictor study. |
| A3.16--A3.17 | Can an external lower-bound continuation contract protect short requests and retain long-request gains? | Yes conditionally: with the short request assigned `0`, and three long summarization requests assigned `64`, a common modeled-positive region exists. | Offline composition of A3.11.  The contract is external; observed horizon is audit-only. |
| A3.18 | What if that declaration is false? | The known short request activated Route A and made the previously safe point negative, quantifying performance—not semantic—risk. | Counterfactual modeled breach, not an online-controller result. |
| A3.19 | How large must the contract be in the observed long traces? | At the selected modeled point, `defer=0` has an observed cross-workload safe suffix at 22 calls; `defer=5` needs 27 and `defer=16` needs 38. | Observed-prefix sufficiency only; it makes no claim beyond the 91/127-call traces. |

## Main artifacts

- Frozen front-end structure: `analysis/longbench_balanced_v2_freeze.json`.
- Frozen Route-B fallback screen: `analysis/b4_route_b_screening_freeze.json`.
- Read-only lifecycle boundary: `analysis/route_a2_lifecycle_freeze.json`.
- Cross-workload contract/policy sweep:
  `analysis/experiments/route_a317_cross_longoutput_contract_policy_01/`.
- Contract-breach sensitivity:
  `analysis/experiments/route_a318_contract_breach_summary_01/`.
- Observed-prefix contract analysis:
  `analysis/experiments/route_a319_long_summary_prefix_contract_01/`.

## Consolidated findings

### 1. Route A has passed the *research-feasibility* gate

The A0 result removes the first major objection: KVzap's irregular token mask
does not prevent compact **capacity** when physical packing happens per head
after maturity.  This is a stronger basis than blockifying or sharing masks,
both of which lose the original logical advantage.

The A2--A3 chain removes the second ambiguity from the model: admission is a
real lifecycle cost, not a zero-cost static compaction.  The resulting models
identify explicit conditions under which that cost can be repaid.  Route A is
therefore a credible architecture research direction and should remain the
main branch rather than returning to Route B by default.

This does **not** mean Route A has passed an implementation, RTL, or measured
speedup gate.

### 2. No-contract deployment has a real performance-risk boundary

With no trustworthy lower bound on remaining generation, two semantic-safe
choices exist:

```text
strict path:       Full KV for the request; zero Route-A gain and zero admission loss
speculative path:  wait D calls, then begin Route-A admission; correct semantics,
                   but short requests can finish just after admission begins
```

The `D=16` example is an intuitive speculative switch point, not a proven
universal optimum.  Its expected cumulative-saving curve is zero before
activation, drops when admission is charged, and may recover only after enough
future sparse reads.  A3.15/A3.18 show why a high output cap cannot guarantee
that recovery.  A future no-contract sweep must measure this curve over a
denser range of `D` and request horizons; do not present its shape as a
universal measured law yet.

### 3. A trusted continuation contract changes the policy, not the data path

A continuation contract is a lower bound supplied by an external API or a
higher-level scheduler; it is **not** inferred from the completed trace and
is not the same as `max_new_tokens`.

```text
trusted N < N_required  -> request-level Full-KV bypass, no admission
trusted N >= N_required -> Route-A fast path, still performs admission/packing
contract breach         -> semantics remain intact; modeled performance can lose
```

At the selected modeled point below, the three long summarization traces have
a common observed-prefix requirement of 22 calls under `defer=0`.  The saving
at that first safe prefix is only about `+0.98%`, so it is a feasibility bound,
not a generous deployment margin.  A contract must be trustworthy, or the
system needs to accept speculative performance risk / select Full KV.

### 4. Current candidate hardware contract (model-derived, not RTL)

The best currently archived common point is:

| Component | Candidate assumption |
|---|---|
| KV front end | Qwen3-8B official KVzap predictor, threshold `-4`, hot window `128` |
| Cold layout | Independent append-only packed page list per `(layer, kv_head)`, `P=64` |
| Admission service | Oldest-first budget `512` retained tokens per `(model call, layer)`, `defer=0` on the trusted-contract fast path |
| Pending mapping | `round_robin_token` |
| Memory-system sweep point | 16 banks, 64-byte bursts, 64 bytes/cycle/bank |
| Staging | at least 8,192 tokens/layer |
| Contract evidence | common observed safe suffix `N=22` across LongGov (127 calls), MultiNews (127), and QMSum (91) |

At that point, the minimum final modeled cycle saving among the three long
workloads is `+40.9644%`; `defer=5` and `defer=16` reduce that minimum to
`+39.0432%` and `+34.8751%`, respectively, while requiring observed prefixes
of 27 and 38 calls.  These are modeled cycle proxies, not speed measurements.

The A3.18 counterfactual breach makes the same `defer=0` candidate's worst
modeled saving `-10.9942%` when the known 17-call retrieval request falsely
declares the long continuation.  Thus the hardware needs a request-level
Full-KV bypass; the software/control plane must choose the path.

## Paper narrative to retain

1. **Problem:** fine-grained KVzap pruning offers logical compression but does
   not by itself specify a compact physical layout or amortize admission.
2. **Physical opportunity:** hot/cold, append-only per-head packing preserves
   the original mask's capacity advantage without forcing block regularity.
3. **System obstacle:** admission, variable per-head lengths, pending-store
   reads, bank/burst effects, staging, and softmax merge can erase the gain.
4. **No-contract result:** speculative admission is semantics-safe but has a
   measurable modeled short-output loss; output caps alone do not solve it.
5. **Contract-gated result:** an external trusted lower bound permits a
   request-level Full-KV/Route-A choice and exposes a modeled-positive
   architecture region; breach sensitivity quantifies why the contract must
   be explicit.
6. **Claim boundary:** this is conditional architecture feasibility, not a
   universal LLM claim, a deployed controller, or measured hardware speedup.

## Decision and next gates

**Decision:** proceed to the next hardware and actual-benefit research stage,
but do not freeze an RTL specification yet.

The next work is split deliberately:

1. **A3.20: no-contract speculative-policy curve.**  Use branch-consistent
   replay to sweep `defer` densely around 0--32 (including 16), plot cumulative
   modeled net saving versus actual decode prefix, and report the probability/
   distribution of loss across more naturally short and long workloads.  This
   establishes the no-contract baseline before using contracts as an optional
   extension. The analysis contract is
   `tools/analyze_kvzap_route_a320_speculative_defer_curve.py`.
2. **A4.0: functional packed-attention reference.**  Build a policy-on,
   semantics-checked packed-cold + pending-staging reference with online
   softmax merge.  Compare it with the applicable official KVzap semantics,
   not silently with a different mask.  Require output/mask/state equivalence
   tests before timing it.
3. **A4.1: measured software-system evidence.**  Instrument the reference on
   named workloads: kernel/runtime breakdown, allocated/reserved memory, and
   device memory-traffic counters where available.  Report them as measurements
   only after controls and repetition; keep them separate from the A3 model.
4. **A4.2: hardware microarchitecture refinement.**  Convert the candidate
   point into interfaces and resource bounds: per-layer FIFO depth, page-table
   format, bank mapping/arbitration, 512-token admission service, pending/packed
   dual-source gather, online-softmax merge, and Full-KV bypass.  Sweep bank
   conflict and burst efficiency with address-preserving traces or a calibrated
   memory model.
5. **Architecture-spec / RTL gate.**  Enter RTL only if A4 verifies semantic
   behavior, the measured path corroborates the relevant modeled trend, the
   no-contract fallback/control policy is explicit, and the resource contract
   is stable across additional models and long-output workload classes.

## Non-claims retained with this archive

- No result here is an actual HBM bandwidth, allocator, wall-clock latency,
  throughput, energy, or silicon-area measurement.
- The lifecycle and shadow collectors do not execute KVzap-pruned sparse
  attention during generation; dense Full KV remains authoritative there.
- `N=22`, `P=64`, the 512-token budget, and the selected bank point are
  Qwen3-8B/workload/model assumptions, not universal constants.
- The long-request contract evidence is currently concentrated in three
  summarization requests; it is not evidence for all LongBench categories,
  all models, ordinary open-ended chat, or reasoning workloads.
- A breach loses modeled performance, not necessarily generation correctness;
  correctness and performance safety must remain separately reported.
