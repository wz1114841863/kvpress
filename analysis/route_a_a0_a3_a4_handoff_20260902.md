# Route-A A0--A3 closeout and A4 handoff — 2026-09-02

## New-conversation entry point

This is a status/handoff record, not an architecture-spec freeze and not a
hardware-performance claim. Read, in order: `AGENTS.md`, `RESEARCH_CONTEXT.md`,
`TRACE_SCHEMA.md`, `KVZAP_ARCHITECTURE_PATH.md`,
`analysis/route_a_research_plan.md`, `analysis/route_a_stage_archive_20260902.md`,
then this document. Preserve frozen traces/results; use a new experiment output
directory and hash-bound provenance for every new run.

## Route-A story at closeout

KVzap's head-specific token mask has high logical compression but irregular
positions. Route A preserves its exact mask and implements:

```text
predict once -> regular 128-token hot window -> mature
             -> drop or append to packed per-(layer, head) cold pages
             -> repeated sparse cold-KV reads
```

A0--A3 established conditional architecture feasibility, not actual speedup:
packed pages preserve the capacity opportunity; admission and variable-length
work require explicit scheduling, FIFO, pending-store, page, bank/burst,
staging, and softmax-merge treatment; a stated hardware model still has a
positive long-output region. With no trusted future continuation, deferred
admission is semantic-safe but performance-speculative. A continuation contract
is an optional control-plane input, not a default assumption or length predictor.

## Evidence ledger

| Stage | Supported result | Boundary |
|---|---|---|
| A0 | Original-mask packed cold pages retain the physical-capacity opportunity. | Static predictor-only replay, not dynamic admission or HBM. |
| A1 | Variable-length head/page work needs explicit scheduling. | Offline simulated batches. |
| A2 | Read-only lifecycle collection passed normal/silent/recorded equivalence guards. | Dense Full-KV remains authoritative. |
| A3.5--A3.11 | Bounded admission, FIFO/page state, pending reads, bank/burst, staging, merge, and scheduler costs are branch-consistent. | Trace-derived state + declared byte/cycle model. |
| A3.12--A3.15 | `max_new_tokens` cannot protect high-cap natural early stop. | Validated 17-call Qasper counterexample. |
| A3.16--A3.19 | An external lower bound enables request-start bypass/fast-path selection; breach can lose modeled performance. | Contract DSE, not online prediction. |
| A3.20 | `D=16` has activation dip then recovery on long-output traces. | One modeled point, long summarization only. |

## Artifact index

- Front-end freeze: `analysis/longbench_balanced_v2_freeze.json`.
- Route-B fallback freeze: `analysis/b4_route_b_screening_freeze.json`.
- Lifecycle freeze: `analysis/route_a2_lifecycle_freeze.json`.
- A0: `analysis/experiments/longbench_balanced_v2_route_a0_packed_pages_01/`.
- A1: `analysis/experiments/longbench_balanced_v2_route_a1_scheduler_01/`.
- A3.17: `analysis/experiments/route_a317_cross_longoutput_contract_policy_01/`.
- A3.18: `analysis/experiments/route_a318_contract_breach_summary_01/`.
- A3.19: `analysis/experiments/route_a319_long_summary_prefix_contract_01/`.
- A3.20: `analysis/experiments/route_a320_longoutput_speculative_curve_local_01/`.

## Current model-derived checkpoint

Candidate point: Qwen3-8B KVzap, threshold `-4`, hot window `128`, page 64,
oldest-first admission budget 512 retained tokens/layer/call, 16 banks,
64-byte burst, 64 B/cycle/bank, `round_robin_token`, and 8,192 staging
tokens/layer. At this point, final modeled cycle saving is `+40.9644%`
(LongGov), `+42.0195%` (MultiNews), and `+46.5624%` (QMSum) for `defer=0`.
The common observed-prefix nonnegative requirement is 22 calls.

For no-contract `D=16`, the three traces dip to `-10.5890%`, `-2.8957%`, and
`-1.8343%` immediately after activation and recover at calls 38, 31, and 25.
This validates the mechanism. Do not make finding more known-negative lengths
the main effort: a negative cumulative ledger is already a loss under the
fixed request/model assumptions. Keep A3.15 as the concrete short-output
control; only extend short-output screening if estimating real risk prevalence.

## Claims allowed now

Allowed: conditional Route-A feasibility; packed capacity opportunity; stated
modeled-positive region; no-contract speculative loss mechanism; optional
contract-based bypass/fast-path policy.

Not allowed: policy-on packed-attention equivalence; actual HBM/allocator/
latency/throughput/energy/area/frequency result; deployed length predictor;
generality beyond Qwen3-8B and named traces; RTL-ready specification.

## A4 objective: close the model-to-execution gap

### A4.0 — policy-on functional packed-attention reference

Build the minimum reference backend that actually reads:

```text
regular hot KV + pending retained cold staging + sealed packed cold pages
```

It must preserve original KVzap mask decisions, positions, page append order,
and hot-window semantics. It must merge partial attention through numerically
stable online softmax. The software-visible request modes are:

```text
Full-KV bypass: no eligible/trusted continuation; zero Route-A admission.
Route-A fast path: explicit selection; admission and packed attention active.
```

Required before timing: hot tokens never cold-pack; mask/positions unchanged;
three-store attention matches same-mask dense reference within declared
tolerance; FIFO/page conservation per call; online merge matches concatenated
reference; answer/state guards are scoped to the applicable KVzap reference,
not silently to Full KV.

Start with a named small request and layer/head harness, then connect to
generation only after those checks pass.

Implementation status (2026-09-02): the no-model, single-layer functional
harness is implemented as `kvzap-route-a40-packed-attention-reference-1.0`.
It has unit guards for exact-mask maturity partition, hot-window exclusion,
oldest-first pending/page conservation, empty/tail/cross-page states,
different head lengths, online-softmax equivalence, and explicit bypass.
This is not yet a model-cache hook, generation-equivalence result, or A4.1
measurement; the next gate is a named small request/layer/head integration.
The remote-capable runner for that gate is
`tools/run_kvzap_route_a40_integration_gate.py`; its protocol is
`analysis/route_a4_remote_run.md`. It is deliberately read-only, so it is not
yet the policy-on generation or A4.1 measurement gate.

The next minimal policy-on gate is intentionally scoped to one Qwen layer/KV
head GQA group during `q_len=1` decode. That group receives no fake-key or
dense cold fallback and must equal a same-mask dense numerical reference; a
separate budget-one run requires non-empty pending staging. This is a semantic
generation gate only. It remains below A4.1 because other heads are dense and
no repeated timing, allocator, or profiler measurements are collected.

The next semantic coverage increment is `target_kv_head=all` within one layer:
every layer-local KV-head GQA group must replace original attention and must
exercise pending staging. It is still not a full-model or measured-performance
claim.

A4.0 now progresses through an early/middle/late `{0,18,35}` shared-predictor
multi-layer gate before the all-layer gate. Each layer owns independent state
and numerical guards; neither gate is a timing result.

The all-layer gate additionally records an execution-dtype ULP diagnostic
limit (default 16) separately from its mandatory FP32 same-mask guard. This
does not relax FP32 packed-versus-dense semantics: it only avoids treating
small post-cast values accumulated through prior substituted low-precision
layers as an attention semantic failure. Any run must preserve the declared
limit and observed maximum in its fresh manifest.

The all-36-layer manifest
`analysis/experiments/route_a40_policy_on_qwen_all_layers_pending_02/` passed
as an A4.0 functional gate: all 36 layers and all eight KV heads were
substituted for seven decode calls (2,016 comparison rows), with actual
pending reads in 1,696 rows and packed-page reads in 1,383 rows. Its maximum
FP32 difference was `1.52587890625e-05`, and its maximum execution-dtype
diagnostic was 13 ULP under the declared 16-ULP limit. These are numerical and
state-coverage diagnostics only; the next step is an independent same-mask
dense KVzap control, not A4.1 measurement.

Independent online dense and Route-A controls are required to compare their
per-layer original-mask digests. A mismatch is a useful A4.0 finding: it must
be diagnosed with the bounded score/keep event report, not hidden by calling
the two paths same-mask. A future replayed-mask pairing would be a separate,
explicitly labelled control.

The next implementation is that replayed-mask paired control: dense KVzap is
the sole online predictor source, while Route-A consumes the frozen dense
events exactly once. It can establish a strict same-mask functional pairing,
but does not erase the observed independent-online drift and is not A4.1.

### A4.0 recorded closeout (2026-09-02)

The replayed-mask control succeeded at
`analysis/experiments/route_a40_policy_on_qwen_all_layers_replayed_mask_01/`.
For Qwen3-8B, threshold -4, hot window 128, page size 64, budget 1, and the
named retrieval request (`max_new_tokens=8`), it replayed dense-source masks
through all 36 layers and all KV heads. Each side produced 2,016 comparisons;
all per-layer decision counts/digests matched and replay consumption was
complete. Route-A comparison rows included 1,696 pending and 1,383 packed-page
reads. Its maximum FP32 difference was `1.52587890625e-05`; the maximum
executed-dtype diagnostic was 13 under the declared 16-ULP limit. Full-KV,
dense, and Route-A answer hashes were equal for this one request.

This closes the A4.0 paired functional gate, not online mask stability: the
separate `route_a40_policy_on_qwen_all_layers_dense_drift_02` diagnostic found
5 threshold flips among 268,992 independent online decisions. It also does not
close A4.1. The measurement plan is
`analysis/route_a41_measurement_plan.md`; it requires measured Full-KV,
same-mask dense replay, and same-mask Route-A replay distributions with
separate component, allocator, profiler, and end-to-end records.

### A4.1.0 harness status (2026-09-02)

`kvpress/route_a_measurement.py` and
`tools/run_kvzap_route_a41_measurement_harness.py` now provide the no-model
measurement contract. Unit tests cover CPU rejection, raw-record byte/schema
validation, warm-up exclusion from summaries, and new-directory-only artifact
writes. The local dry-run artifact
`analysis/experiments/route_a41_harness_dry_run_01/` passed without touching
CUDA or loading Qwen. It is not a model timing, allocator, or profiler result.
The next remote gate is only the harness's CUDA tensor-add self-check; do not
start component or decode measurement until that new artifact is reviewed.

### A4.1.1 implementation status (2026-09-03)

The A4.1.1 one-layer/head component-gate code is now staged.
`tools/collect_kvzap_route_a41_replay_source.py`
collects one untimed online dense-KVzap score/keep event stream, hashes it,
and records its request/config provenance.  The separate
`tools/run_kvzap_route_a41_component_gate.py` consumes that source exactly in
both replayed paths.  It records raw, warm-up-labelled CUDA-event/host samples
and PyTorch allocator snapshots for dense-cold versus Route-A maturity,
admission/page-table, hot/pending/packed attention, and merge.  Its optional
online predictor control is a distinct unpaired path.

The callback timer synchronizes every measured component, so A4.1.1 is a
micro-component attribution gate, not end-to-end decode timing.  The first
remote run must use `admission_budget=1` and require observed pending staging;
the separate `admission_budget=512` candidate-point run follows only after the
budget-one artifact is reviewed.  It must use a fresh replay-source directory
or an already validated provenance-bound source, plus a fresh result directory;
neither A4.0 output nor frozen trace is edited.

The first accepted artifact pair is
`route_a41_replay_source_layer0_budget1_01` and
`route_a411_component_layer0_head0_budget1_02`.  The replay NPZ SHA-256 agrees
with both manifests (`1cf570...6151ef5`), and all 26 path repetitions share
the source answer digest.  Its 3 warm-ups and 10 reported repetitions per
replayed path have complete mask consumption.  At `budget=1`, selected head 0
has 7 decode comparisons, `max_pending_tokens=21`, and
`max_packed_tokens=1`; this is the intended pending-staging coverage point.
The recorded CUDA-event/host figures are synchronized Python-reference
micro-component observations only.  They are not an end-to-end decode result,
Full-KV comparison, HBM measurement, allocator delta, throughput, or hardware
claim.  The next separate candidate point is `budget=512`; it omits the
explicit pending-nonempty guard because an empty pending FIFO is then valid.

The rerun `route_a411_component_layer0_head0_budget1_03` records that explicit
guard.  It and `route_a411_component_layer0_head0_budget512_01` share the
same replay event SHA-256 and source digest, have one identical answer digest
over all path runs, and complete every replay.  State coverage changes exactly
as intended: budget one reaches pending/packed maxima of 21/1, whereas budget
512 reaches 0/22.  This is a software-state and component-observation result,
not a speed comparison.  The summary's 70/280 counts are callback invocations
within 10 reset runs. The next schema-1.1 runner emits both callback and
per-reset-run aggregate distributions; the latter sums component callback time
and takes a run-local allocator peak maximum before comparing variance across
points.

The next A4.1.1 increment is layer 0/KV-head 6. The recorded replay source
has a head-6 dense-cold maximum of 195 tokens, unlike head 0's 22. The new
component gate records packed page count, full-page count, and tail occupancy,
and the head-6 budget-512 run must use `--require-multi-page-packed`. This
establishes only actual multi-page state coverage in the Python reference; it
does not establish a page allocator, HBM behavior, or end-to-end performance.

The accepted head-6 artifacts are
`route_a411_component_layer0_head6_budget1_summary11_01` and
`route_a411_component_layer0_head6_budget512_multipage_01`. Both use the
validated layer-0 replay source, complete replay consumption, and have ten
reported reset runs per component aggregate. Budget one has pending/packed
maxima of 191/5 and no full page; budget 512 has pending zero, packed 195,
four packed pages, three full sealed pages, and a separately observed tail
occupancy watermark of 63. The maxima need not occur in the same decode call.
This closes A4.1.1 state/component coverage for the named layer/head and two
admission points. It authorizes A4.1.2 **infrastructure** work only: a
whole-decode region must be timed once per reset run with no per-component
synchronization, first for replayed dense/Route-A at `{0,18,35}`, and only
then broadened. It does not authorize an A4.1.2 performance conclusion yet.

The A4.1.2 runner is now implemented as
`tools/run_kvzap_route_a412_whole_decode_gate.py`, but has no accepted
real-Qwen output. It uses a fresh cache/state per run, leaves context prefill
outside timing, and measures exactly one question-forward plus greedy-decode
region. It emits separate Full-KV bypass, same-mask dense replay, and
same-mask Route-A replay rows in seeded shuffled order. The first real gate
requires a newly collected `{0,18,35}` replay source and all selected KV heads.
Its timings characterize this Python reference only, not prefill, HBM,
throughput, energy, hardware acceleration, or RTL.

The first accepted A4.1.2 artifact is
`route_a412_whole_decode_layers_0_18_35_budget512_01`, with source
`route_a412_replay_source_layers_0_18_35_01`. It has 39 raw rows (9 warm-up,
30 reported), one timed question-forward-plus-greedy-decode region per path
run, and complete replay for 3 layers × 8 KV heads × 7 decode calls. All
paths happened to generate the same eight token IDs on this request. Measured
CUDA-event means are 290.50 ms Full-KV, 1347.80 ms replayed dense, and 1608.48
ms replayed Route-A; Route-A is 19.3% above dense replay here. This is a
negative performance observation for the current Python reference, not for
the Route-A architecture: native dense DynamicCache is still retained while
the reference copies K/V into dense/packed shadow state. Dense and Route-A
allocator peaks are equal, so no storage-saving conclusion is available.
Before an all-layer or cross-workload run, add one documented profiler
diagnostic per path and use it to scope a separate true cache-ownership/
storage-substitution design.

**A4.1.2.1 implementation (awaiting a fresh remote capture):**
`tools/run_kvzap_route_a412_profiler.py` runs one separately labelled
`torch.profiler` diagnostic for each paired A4.1.2 path after untimed context
prefill and fresh-cache warm-up. It requires the hashed replay source and
exports per-path Chrome traces, normalized operator tables, answer/token-ID
digests, replay coverage, and PyTorch allocator snapshots. Profiler output is
not a timing repetition and must never be merged with A4.1.2 latency
distributions. Its sole purpose is to identify Python reference overhead
before separately designing true cache ownership and storage substitution.

The first 1.0 capture is a valid raw-trace diagnostic but its normalized
operator summary read legacy `cuda_time_*` aggregate attributes that PyTorch
2.10 leaves empty. It is not a K/V read, mask, replay, or attention-semantic
failure: replay guards and answer/token digests passed. The runner is now
schema 1.1 and reads `device_time_*` first, with legacy fallback. Rerun the
diagnostic into a new directory to obtain usable GPU operator ranking; retain
the prior directory as a provenance record. Chrome trace JSON is expected to
be large and may be losslessly gzip-compressed for transfer.

**A4.1.2.2 implementation (awaiting two fresh remote gates):**
`tools/run_kvzap_route_a4122_cache_ownership_gate.py` targets one `(layer,
kv_head)`. It uses an ownership-specific Route-A backend that copies original
K/V into Route-A state and then NaN-poisons the selected mature-cold cells in
the native DynamicCache view. Every later call verifies those cells remain
poisoned, so selected policy attention cannot silently recover cold K/V from
native dense cache. Schema 1.1 records same-mask dense/owned-cold generated
token drift but does not reject it: per-head FP32 guards and finite Route-A
decode output are the semantic checks. Native tensor slots remain allocated by design; the
manifest must state `native_cold_slots_physically_freed: false`. First run
layer 0/head 6 at budget one with pending required, then budget 512 with
multi-page required. Neither run is a timing or storage-saving measurement.

**A4.1.2.3 implementation (awaiting a fresh remote prefix diagnostic):**
`tools/run_kvzap_route_a4123_first_decode_logits_diagnostic.py` runs context
prefill plus only the question forward and emits bounded first-generation
logit diagnostics for Full-KV, same-mask dense, and owned-cold Route-A. It
does not greedily generate or require full replay consumption. Record the
question token length and Route-A q_len=1 call count: a nonfinite Route-A
logit with zero policy calls establishes that a multi-token native fallback
consumed poisoned native cold K/V, rather than a benign online-softmax drift.

**A4.1.2.4 implementation:** `tools/run_kvzap_route_a4124_multitoken_bridge_gate.py`
adds a causal selected-head question-forward bridge. It advances Route-A state
one question token at a time and replaces selected outputs, while native
attention sees zero placeholders for selected heads. The next remote gate must
require finite logits, equal first argmax, full bridge-token count, and prior
poison-read coverage; it remains untimed and prefix-only.

**A4.1.2.4 schema 1.1 correction:** the same-mask dense control now also uses
a causal selected-head bridge for q_len>1. The preceding 1.0 artifact is useful
for proving the Route-A bridge no longer produces NaNs, but it is not a valid
numeric Route-A-versus-same-mask-dense comparison because its dense selected
heads fell back to native Full-KV. The new manifest records bounded per-token
attention-error summaries for the valid paired comparison; it remains a
single-layer/head, prefix-only semantic diagnostic.

**A4.1.2.4 schema-1.1 result:**
`analysis/experiments/route_a4124_multitoken_bridge_layer0_head6_budget1_densebridge_01/`
completed with the immutable layer-0 replay source hash
`1cf570185922d76d8924eaa193aa9831537b9523c0c6b0871765218096151ef5`. Both
same-mask dense and owned-cold Route-A bridged all 22 question tokens; the
Route-A per-head guard observed `5.21540641784668e-08` maximum FP32 difference
and one executed-dtype ULP, while their final logits had zero maximum absolute
difference. Full-KV versus same-mask dense was `0.55078125`, so the former
schema-1.0 `0.55078125` Route-A delta is attributable to comparing against the
native Full-KV fallback rather than a same-mask dense control. This validates
only the narrow single-layer/head prefix numerical path; it does not establish
KVzap quality, answer equivalence, full decode, timing, allocator memory, HBM,
or hardware benefit.

**Next A4.1.2.5 gate:** run the same valid paired bridge with head 6 and
`admission_budget=512`, requiring actual multi-page, sealed full-page, and tail
page coverage. This is deliberately complementary to the budget-one pending
gate: it validates page-boundary semantics under a high admission configuration
without asserting that pending staging must remain nonempty. The current runner
implements these as explicit observed-state guards in schema 1.2.

**A4.1.2.5 result:**
`analysis/experiments/route_a4125_multitoken_bridge_layer0_head6_budget512_multipage_01/`
completed with all requested observed page guards. At the bridge, layer 0/head
6 had 191 packed retained tokens, three pages, two sealed full pages, and a
63-token tail; no pending token remained under budget 512. Both same-mask
bridges covered all 22 question tokens, ownership poisoning was rechecked, and
same-mask dense/Route-A final logits were equal with one maximum execution
dtype ULP at selected attention. This is valid multi-page functional evidence
for one head only.

**A4.1.2.6 implementation boundary:** schema 1.3 generalizes native-cold
ownership from one explicit KV head to all KV heads of layer 0 simultaneously,
retaining per-head GQA mapping and coverage records. The runner now requires
every selected head to bridge every question token, and supports aggregate
pending/page-state guards. Initial all-head gates separately cover budget-one
pending and budget-512 head-6 multi-page conditions. Aggregate page-state
requirements are necessary because replay evidence shows that not every head
retains enough mature cold tokens for a full page. Do not proceed to multi-layer
ownership or timing until both same-layer all-head semantic gates pass.

**A4.1.2.6 result and hold:**
`route_a4126_allheads_layer0_budget1_pending_01` and
`route_a4126_allheads_layer0_budget512_multipage_01` each resolved all eight
layer-0 KV heads and produced 22 comparisons per head. The first observed
pending on five heads; the second observed head 6 with three packed pages, two
full pages, and a 63-token tail. Ownership poisoning and the per-attention
same-mask contract passed (at most one execution-dtype ULP). But the paired
same-mask dense/Route-A final logits differed by `0.44921875`, although first
argmax remained equal. This is compatible with downstream amplification of
many one-ULP replacements but is not yet localized; do not extend to multi-
layer ownership. The schema-1.3 manifest also encodes unrequested page guards
as vacuous true values; read requested state from config and observed state from
coverage, and correct this metadata in the next diagnostic schema without
editing the completed artifacts.

**Next implementation boundary:** add an untimed all-head downstream
accumulation diagnostic that captures only bounded activation-difference
summaries per question token and transformer layer for paired same-mask dense
and Route-A forwards. It must establish whether the delta starts after the
replaced layer-0 attention and propagates through unchanged layers, or exposes
a cross-head/state error. Only after that localization passes may simultaneous
ownership expand to `{0,18,35}`.

**A4.1.2.7 implementation:**
`tools/run_kvzap_route_a4127_allhead_activation_diagnostic.py` is the bounded
all-head downstream locator. It runs paired same-mask dense and Route-A layer-0
all-head question forwards, captures transient output activations for all 36
decoder layers, and serializes only per-layer/per-question-token scalar
relations. It also replaces vacuous guard booleans with explicit requested /
satisfied metadata. Run budget one pending coverage before budget 512 multi-
page coverage; inspect this localization before any multi-layer ownership work.

**A4.1.2.7 budget-one result:**
`route_a4127_allheads_layer0_budget1_pending_activation_01` captured all 36
question-forward decoder layers without serializing activations. Its first
paired dense/Route-A difference occurs at selected layer 0, then grows through
later unchanged layers (relative L2 from `0.0002011` at layer 0 to `0.01665` at
layer 35); all values are finite and the first argmax remains equal. This
supports downstream numerical propagation rather than a pre-target or
ownership-bypass error. The budget-512 multi-page counterpart remains required
to test whether this behavior is invariant to pending-versus-packed page state.

**A4.1.2.7 budget-512 result:** the synchronized multipage artifact (directory
suffix `_0`) has the same first-difference layer and the same 36-layer scalar
propagation table as budget one, while exercising head 6's three-page/two-full-
page/63-tail packed state. Thus, for this fixed layer-0 all-head replay prefix,
the observed final-logit drift is invariant to pending versus packed-page
admission state and is localized to downstream numerical propagation. This is
not yet a quality, complete-decode, timing, memory, or multi-layer result.

### A4.1.2.8 next gate — bounded continuation consequence of the all-head drift

The `0.44921875` final-logit maximum in A4.1.2.6/7 is not itself an answer
error or an error percentage. It was recorded with equal first argmax, but a
later greedy decision can change if a later margin is sufficiently small.
`tools/run_kvzap_route_a4128_allhead_continuation_diagnostic.py` therefore
runs an untimed 8-token same-mask continuation in three forms: dense greedy;
Route-A forced to consume the dense token IDs (a same-input paired logit check
at every offset); and independent Route-A greedy (a first-token-mismatch
observation). Its fixed count must exhaust the replay source. Rows after an
independent mismatch have different inputs and are explicitly not numerical
paired comparisons. Run first with budget-one pending coverage, then with
budget-512 aggregate multi-page/full-page/tail coverage. Do not interpret this
as quality, Full-KV equivalence, timing, allocator/HBM, or multi-layer evidence.

**Observed A4.1.2.8 budget-one result (2026-09-04):**
`route_a4128_allheads_layer0_budget1_pending_continuation_02` completed with
pending-state coverage and complete shared replay consumption for all three
paths. Over the declared eight-token horizon, forced Route-A had equal paired
argmax at every offset and independent Route-A generated exactly the same token
IDs as dense. Its largest per-offset logits maximum was `0.640625`, while the
smallest dense top-1/top-2 margin was `21.5`. No token-level greedy consequence
was observed for this fixed layer-0/all-head/pending replay, but page-state,
longer-horizon, multi-layer, quality, and performance questions remain open.

**Observed A4.1.2.8 budget-512 result (2026-09-04):**
`route_a4128_allheads_layer0_budget512_multipage_continuation_01` additionally
passed aggregate multi-page/full-page/tail coverage: head 6 reached four
packed pages, three full pages, and a 63-token tail, while pending correctly
drained to zero. The shared replay was again complete; forced argmax and the
independent eight-token greedy sequence matched dense exactly. Its per-step
paired-logit relation table is exactly the budget-one table, controlling the
pending-versus-packed layout variable for this fixed layer-0 all-head horizon.
Next create a fresh replay source for layers `{0,18,35}` and repeat this
forced/independent all-head continuation diagnostic there before any all-36
layer or timing expansion.

### A4.1.2.9 next gate — `{0,18,35}` simultaneous ownership

First collect a new immutable replay source for precisely layers `{0,18,35}`;
the old layer-0 source cannot be reused because each selected layer needs its
own original-mask events. The new
`tools/run_kvzap_route_a4129_multilayer_continuation_diagnostic.py` attaches
all-head same-mask dense or native-cold ownership Route-A backends to the three
layers simultaneously. It preserves the A4128 forced common-token and
independent greedy distinction, but requires bridge/replay/ownership coverage
per layer. Run pending coverage at budget one before page-boundary coverage at
budget 512. Do not expand to all 36 layers or timing unless the multi-layer
gate remains finite and has no forced/independent greedy divergence; this is
still no quality, Full-KV, allocator/HBM, or performance result.

**Observed A4.1.2.9 budget-one result (2026-09-04):**
`route_a4129_layers_0_18_35_budget1_pending_continuation_01` completed all
three per-layer replay/bridge/ownership audits, with aggregate pending staging
coverage. Forced and independent Route-A both matched the same-mask dense
eight-token greedy sequence. The maximum final-logit delta was `0.5`, while
the minimum dense top-1/top-2 margin was `20.0`. This is sufficient to run the
same-source budget-512 page-state counterpart; it does not authorize an
all-36, quality, timing, allocator/HBM, or hardware claim.

**Observed A4.1.2.9 budget-512 result (2026-09-04):**
the three-layer page-state companion passed aggregate multi-page/full-page/tail
coverage, all per-layer replay/bridge/ownership audits, and both continuation
relations. Its largest final-logit difference was `0.75`, compared with a
minimum dense decision margin of `20.0`; no forced argmax or independent token
changed. The scalar logit relation is not bitwise identical to budget one,
which is valid numerical-layout variation rather than evidence of a read
error. The pending-versus-packed variable is now controlled for `{0,18,35}`.
Next create an all-36-layer immutable source and repeat budget-one semantic
continuation before its page-state counterpart; do not begin timing yet.

### A4.1.2.10 implementation — all 36 layers

`tools/run_kvzap_route_a4130_alllayer_continuation_diagnostic.py` now wraps the
validated multi-layer continuation core with a strict all-layer scope. It
rejects partial `--target-layers`, uses a distinct schema/manifest, and retains
separate replay state and ownership guards per decoder layer. First produce a
new immutable all-layer source, then run only the budget-one pending gate and
inspect it before the budget-512 page-state companion. This is still an
untimed same-mask semantic check, not the true storage-substitution or A4.1
performance phase.

The A4130 runner also persists a bounded scalar numerical-guard failure record
before aborting on an execution-dtype ULP breach. Do not raise the ULP limit
without reviewing its layer/head/position and paired FP32 evidence. Preserve the
failed fresh directory and rerun the same immutable replay source only into a
new directory after synchronization.

**A4.1.2.10 budget-one numerical hold (2026-09-04):** the all-36 forced path
stopped at layer 8/head 3/query head 15/cache position 916 because a near-zero
BF16 component had 26 local ULPs over the 16-ULP diagnostic limit. Its absolute
cast difference was `3.0268e-09` and the vector maximum FP32 difference was
`1.7136e-07`, below the hard `atol=1e-5` guard. This does not implicate replay
masking or native-cold ownership, but it prevents an all-36 completion claim.
Do not run budget 512 or raise the limit. First add a bounded record-only
all-layer ULP distribution diagnostic, retaining the FP32 guard.

### A4.1.2.11 implementation — bounded all-layer ULP distribution

`tools/run_kvzap_route_a4131_alllayer_ulp_distribution_diagnostic.py` now
provides that next diagnostic. It is pinned to all 36 layers and `record_only`
for the executed-dtype ULP response; users cannot silently select a partial
layer set or change it back to an enforcing run through this entrypoint. It
still hard-enforces FP32 same-mask attention, immutable replay consumption,
causal bridge coverage, and native-cold ownership. Each selected layer emits
only bounded scalar ULP-breach fields (count, maxima, and sample-limited
locations/differences). Its completion is not all-layer acceptance and does not
authorize budget-512, timing, allocator, HBM, quality, hardware, or RTL claims.

### A4.1.2.12 implementation — hard scale-aware cast guard

`tools/run_kvzap_route_a4132_alllayer_scale_aware_continuation_gate.py` is the
next strict rerun, using the immutable all-layer source and budget one. It
retains A4131's scalar ULP distribution but makes a second guard hard: after
casting Route-A and same-mask dense outputs to the execution dtype, the actual
vectors injected into Qwen must pass the declared `torch.testing.assert_close`
`rtol`/`atol`. A failure is scalar-only and identifies the greatest
observed/allowed tolerance ratio. This is a principled replacement for using a
fixed local-ULP count near zero as the sole hard criterion; it is not a relaxed
tolerance, a quality result, or permission for budget-512/timing work until its
fresh output is reviewed.

**A4.1.2.12 observed hold (2026-09-04):** layer 1/head 7/query head 31/position
915 produced adjacent BF16 values near `0.0093`: one ULP (`6.1035e-05`) apart,
but with only `1.1176e-07` maximum FP32 difference. The direct post-cast
FP32-derived allowance `1.0908e-05` is therefore not quantization-aware.

### A4.1.2.13 implementation — hard quantization-aware cast envelope

`tools/run_kvzap_route_a4133_alllayer_quantization_aware_continuation_gate.py`
keeps A4132's hard FP32 guard and ULP observations, but makes the cast bound
the FP32 allowance plus Route-A and dense local execution-dtype ULPs. It permits
the independently rounded adjacent-BF16 case while still rejecting a cast error
outside the FP32-plus-rounding envelope. It remains an all-layer, replayed-mask,
budget-one semantic gate; do not begin budget-512 or timing before review.

**A4.1.2.13 observed result (2026-09-04):** the all-36 budget-one gate
completed against the 268,992-event source with full replay, bridge, ownership,
pending, FP32, and quantization-aware hard-guard coverage. Forced and
independent eight-token outputs matched same-mask dense. The seven >16-ULP
events remained serialized as observations. This clears only the next page-state
semantic scope.

### A4.1.2.14 implementation — all-layer budget-512 page state

`tools/run_kvzap_route_a4134_alllayer_quantization_aware_page_state_gate.py`
is the separate budget-512 entrypoint. It hard-pins admission budget 512 and
requires multi-page, sealed-full-page, and tail-page flags at CLI validation;
it does not require pending. It retains the all-layer replayed-mask,
quantization-aware, ownership, forced, and independent contracts. Do not treat
its result as timing, allocator, HBM, quality, hardware, or RTL evidence.

### A4.1.3.0 implementation — logical storage-ownership contract

`kvpress/route_a_storage_contract.py` now formalizes the future cache-adapter
precondition: preserve logical cache length and native hot positions while
Route-A owns every mature retained record in pending/packed state and drops the
rest under the original mask. The no-model A4135 gate passed both pending and
multi-page/full-page/tail synthetic cases. It explicitly reports native cold
slots as not physically freed, so it neither replaces `DynamicCache` nor
authorizes allocator/timing claims. The next implementation must use this
contract to build a real adapter, first at minimal layer/head scope.

### A4.1.3.1 implementation — external selected-head cold-storage adapter

`kvpress/route_a_external_cold_storage.py` implements that first no-model
adapter without falsely presenting it as a drop-in `DynamicCache`. For an
explicit selected-head set it retains a bounded physical hot K/V tensor,
tracks logical cache length separately, and assigns every mature retained
record to Route-A pending/packed storage. A dedicated unit regression shows
why a stock DynamicCache cannot be physically truncated in place: its reported
sequence length becomes the new physical length. A4136 exercises two append
segments, selected-head same-mask attention, pending budget-1, and packed
budget-512 multi-page/full-page/tail state. It still neither attaches to Qwen
nor frees native DynamicCache slots; no measurement conclusion is authorized.

### A4.1.3.2 implementation — Qwen external-cold interface gate

`RouteAQwenExternalColdStorageAttentionBackend` is the minimal Qwen-specific
bridge. It consumes Qwen's normal post-cache-update K/V only for the newly
scored positions, feeds those into the external adapter under replayed original
mask decisions, and substitutes selected attention from Route-A state. The
existing native-cold poison/read check remains a negative guard, not an
allocator mechanism. A4137 is single layer/head, untimed, and pairs a Full-KV
bypass, same-mask dense control, and external-cold Route-A path. It must retain
both `transformers_dynamic_cache_substitution: false` and
`native_dense_cold_slots_physically_freed: false`.

The adapter preserves admission epochs: a normal Qwen prefill chunk is one
Route-A append/service event, while causal multi-token bridge tokens append
separately. Applying token-level admission to prefill would spend budget one
once per token and falsely erase pending staging.

### A4.1.3.3 implementation — Qwen native-storage replacement prototype

`kvpress/route_a_qwen_cache.py` is the first genuine Qwen `Cache`-interface
prototype, intentionally constrained to layer 0 and one KV head. Persistent
target-layer dense tensors exclude the selected head entirely; Route-A external
state owns that head's hot/pending/packed retained positions and mask drops are
absent. To satisfy Qwen's existing dense attention function, each `update`
returns a transient full-shaped attention view with unreadable selected history
and the current selected K/V segment. The policy backend overwrites selected
attention outputs. A4138 must prove both cache/adapter logical-position
agreement and zero persistent selected mature-cold tokens. It is an untimed
semantic gate, not a physical-memory or performance result.

### A4.1.3.4 implementation — budget-512 page-state counterpart

A4139 wraps the same Qwen cache interface with a fixed budget of 512 and
pre-model checks for multi-page plus tail coverage. The gate requires a newly
collected layer-0/budget-512 replay source and verifies selected persistent
mature-cold absence while packed pages include at least one sealed page, a
second page, and a nonempty tail. It deliberately does not require pending at
this budget and remains a no-timing semantic test.

### A4.1.3.5 implementation — layer-0 all-head replacement

A4140 generalizes the Qwen cache prototype from one selected head to an
explicit selected-head set, initially all eight layer-zero KV heads. Persistent
dense target-layer storage therefore has no KV-head tensor at all; the Route-A
external adapter owns each head's hot/pending/packed state. The gate checks all
GQA groups, cache/adapter logical length, zero persistent selected mature cold,
and aggregate pending coverage. Heads with zero original-mask retained cold are
still substituted and must be recorded rather than silently omitted. This is
not timing or physical-memory evidence.

### A4.1 — measured software-system evidence

After A4.0 passes, collect repeated, explicitly warmed measurements separately:
admission/gather/pack/page-table time; packed/pending/hot attention and merge
time; end-to-end decode; allocated versus reserved memory; and documented
profiler memory-traffic counters. Use both Full KV and same-mask dense KVzap as
distinct baselines. Distributions and raw repetitions are required.

### A4.2 — microarchitecture refinement

Convert validated A4 state/interfaces into constraints for FIFO depth and
overflow, page-table entry format, allocator/seal behavior, admission service,
bank mapping/arbitration, burst efficiency, gather formats, merge state,
scheduler/PE interface, and bypass switching. Bind each parameter to A4
measurement or explicit sensitivity range; do not begin RTL yet.

## RTL gate

Freeze `analysis/architecture_spec.md` only after A4.0 semantics/state tests,
A4.1 measurements, explicit bypass/contract behavior, and cross-model/
cross-workload resource stability all hold.

## First actions in a new conversation

1. Verify checkout and `git status`; preserve unrelated work.
2. Read the documents listed above and inspect source manifests/hashes.
3. Label every proposed result trace-derived, modeled, or measured.
4. Propose A4.0 state/interface plus tests before editing model code.
5. Do not run a model or long benchmark without a small gate and new output dir.
