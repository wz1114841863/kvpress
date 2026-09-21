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

### A4.1.3.6 implementation — all-head budget-512 page-state replacement

A4141 fixes the A4140 all-head interface at admission budget 512 and requires
one witness head to cover a sealed full packed page, multi-page state, and a
nonempty tail. The requirement is intentionally aggregate: any head with zero
retained mature cold under the replayed original mask remains substituted and
must be reported, rather than forcing an invalid per-head page condition.
Persistent selected mature-cold K/V remains absent from the custom cache. The
gate is no-timing semantic evidence only.

### A4.1.3.7 implementation — three-layer all-head replacement

A4142 extends the custom cache interface from layer zero to `{0,18,35}` while
keeping independent Route-A external adapters and all KV heads at each selected
layer. The budget-one gate requires a matching three-layer replay source and
aggregate pending coverage. Each target layer must retain zero persistent
selected mature-cold K/V; non-target layers remain native Qwen cache state.
This is an untimed semantic interface gate only and precedes the matching
three-layer budget-512 page-state counterpart.

### A4.1.3.8 implementation — three-layer all-head budget-512 page state

A4143 fixes the A4142 multi-layer interface at admission budget 512. It first
requires a separately collected three-layer/budget-512 replay source, then
requires one aggregate layer/head witness with a sealed full page, multi-page
state, and a nonempty tail. Zero-retained heads remain valid substitutions;
every target layer must nevertheless retain zero persistent selected
mature-cold K/V. Pending is intentionally not required. This is no-timing
semantic evidence only.

### A4.1.3.9 implementation — all-layer all-head replacement

A4144 generalizes the custom cache interface to every Qwen layer and every KV
head under budget one. It requires the literal all-layer selector and the
matching all-layer/budget-one replay source. Each layer has an independent
external Route-A adapter and must expose zero persistent selected mature-cold
K/V plus zero unselected heads; pending is an aggregate required state. This
is untimed semantic evidence only, before any all-layer budget-512 page-state
counterpart.

### A4.1.3.10 implementation — all-layer all-head quantization-aware replacement

A4145 is the explicit follow-up when A4144 encounters an execution-dtype ULP
outlier. It does not relax the FP32 same-mask guard. Instead, it retains
bounded scalar ULP records while enforcing the existing quantization-aware
executed-dtype close envelope, which distinguishes expected local cast
rounding from unexplained error. All layer/head replay, external ownership,
and persistent-cache-absence conditions remain hard. The result is still
untimed semantic evidence only.

### A4.1.3.11 implementation — all-layer all-head budget-512 page state

A4146 adds the matching all-layer/all-head native-storage page-state gate. It
requires an independently collected all-layer budget-512 replay source, so
admission epochs and packed-page state cannot be borrowed from the budget-one
run. It retains the A4145 FP32, quantization-aware cast, replay, and ownership
guards, records bounded scalar ULP breaches, and requires one aggregate
full-page/multi-page/nonempty-tail witness. Pending staging is intentionally
not required. This remains untimed semantic evidence only.

### A4.1.4 implementation — repeated external-storage whole-decode measurement

A4147 is the first repeated software measurement that uses the real A4.1.3
external-cache interface rather than a `DynamicCache` Route-A reference. It
holds the A4146 all-layer/all-head/budget-512 replay source fixed and compares
Full-KV bypass, same-mask dense replay, and same-mask external-storage Route-A
in seeded shuffled reset runs. Context prefill/cache construction is outside
the timed region; question forward plus greedy decode is timed with CUDA events
and wall clock, and PyTorch allocator snapshots are recorded before/after it.
Every Route-A reset run reasserts replay, ownership, page coverage, FP32, and
quantization-aware numerical guards. It is measured Python-reference software
evidence only; profiler, traffic counters, and hardware conclusions remain
separate.

### A4.1.5 implementation — external-storage profiler attribution

A4148 is the separate profiler follow-up to A4147. It uses the identical
all-layer/all-head, budget-512 immutable replay source and captures exactly one
post-prefill question-forward plus greedy-decode profiler region for Full-KV
bypass, same-mask dense replay, and Route-A external storage. It preserves
external-cache ownership, replay, page-state, FP32 and quantization-aware
guards. Its default output is a bounded top-operator summary; Chrome traces
are opt-in because they can be large. It is an overhead-attribution diagnostic,
not a timing repetition or any HBM/kernel/throughput/hardware conclusion.

### A4.1.6 implementation — phase-attributed profiler

A4149 follows A4148 only to localize its generic profiler operators. It uses
the same all-layer/all-head/budget-512 replay source but tags existing reference
operations with optional nested `route_a_phase::` profiler ranges. The tags
cover external-cache materialization, admission/page work, hot/pending/packed
partials, online merge, same-mask dense reference, numerical guards and scalar
summaries. They make no semantic or policy change, are not timing repetitions,
and must not be summed because profiler ranges are inclusive.

### A4.1.6.1 implementation — paired phase coverage repair

A4150 repairs an A4149 attribution reporting gap without changing Route-A:
the dense multi-token bridge is now phase-labelled, CPU/CUDA split profiler
views are coalesced without doubling invocation counts, and a hard coverage
check binds tagged selected-head attention calls to backend decode plus
multi-token policy execution. It repeats only the paired profiler diagnostic;
its ranges remain nested reference-overhead evidence, not timing results.

### A4.1.7.0 implementation — guard-elided execution certification

A4151 retains the all-layer external storage policy/state/ownership path while
turning off only its per-query numerical-reference checks. It first certifies
that fixed-request forced full-model logits and independent greedy tokens match
the guarded Route-A reference. It is untimed, scalar-only and prerequisite
evidence for a later execution-mode measurement, not a replacement for guards.

### A4.1.7.1 implementation — certified execution-mode measurement

A4152 requires the matching completed A4151 Route-A certificate and separately
repeats a guarded versus execution-only semantic certificate for same-mask
dense KVzap. It then measures fresh-cache whole decode after untimed context
prefill for Full-KV bypass, same-mask dense execution-only, and Route-A
external-storage execution-only. Timed runs retain replay and cache-ownership
guards, and are rejected if their per-path token digest drifts from the
certificate or another reset run. Its timing/allocator distributions are
explicitly separate from guarded A4.1.4 and profiler observations.

The initial A4152/A4153 execution-only attempt is not accepted as a paired
measurement: profiler labels revealed that the dense multi-token bridge still
performed numerical reference work. The repair adds an actual per-layer guard
work counter and makes zero work a hard execution-only invariant; rerun under
a new output directory before interpreting dense/Route-A comparison numbers.

### A4.1.7.3 implementation — empty-source elision

A4154 tests a semantics-preserving candidate that omits only empty Route-A
source partials. It compares forced logits and independent greedy tokens to an
unelided execution-only baseline while retaining replay, external ownership,
page and numerical-work guards. The named budget-512 request must demonstrate
an empty-pending skip while still reading hot and packed sources; it remains
untimed.

### A4.1.7.4 implementation — paired empty-source-elision measurement

A4155 consumes the completed A4154 semantic manifest before timing two
all-layer/all-head external Route-A variants: unelided reference and the
empty-source-elided candidate. It uses adjacent fresh-reset pairs with random
within-pair order, captures PyTorch allocator peaks and execution-only source
call counters, and keeps raw per-pair deltas alongside callback/reset-run
distributions. It is an attribution measurement for the one elision change;
it neither supersedes the distinct Full-KV/same-mask-dense A4152 controls nor
constitutes a packed-kernel, HBM, hardware, or RTL result.

### A4.1.7.5 implementation — paired empty-source-elision phase profiler

A4156 is a separate profiler-only diagnostic that consumes a completed A4155
manifest. It captures one coalesced phase profile each for unelided and
empty-source-elided Route-A, while requiring replay/ownership/page/token
guards plus complete per-source partial-or-skip accounting. Its purpose is
attribution of the A4155 software observation; profiler ranges are nested and
must not be treated as timing, HBM, hardware, or RTL evidence.

### A4.1.7.6 implementation — multi-batch reproducibility gate

A4157 repeats the semantically certified A4155 pair across independent
batches, preserving every signed pair delta and reporting batch/aggregate
median absolute deviation. Device-global nvidia-smi telemetry is sampled
outside timed work solely to contextualize variance; no process inspection or
hardware-counter claim is made. It retains all replay/ownership/page/token
guards and does not turn the Python-reference result into hardware evidence.

### A4.1.7.2 implementation — execution-only paired profiler

A4153 captures one coalesced phase-profiler diagnostic each for same-mask dense
execution-only and Route-A external-storage execution-only after validating the
A4151 certificate and freshly certifying dense. It retains replay, page and
ownership guards plus exact phase-label coverage. Its nested profiler ranges
localize remaining Python-reference work only; they are not a timing result or
hardware cost estimate.

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

### A4.1.7.7 implementation — second-workload source provenance

The replay-source collector now records selected-layer/per-head mask-event
coverage and can require exact configured KV-head IDs. A new summarization
source must be collected independently before any A4151/A4154/A4157 reuse;
this is source provenance only and not a state, timing, HBM, hardware, or RTL
result.

A4151 may now require and record the collector's exact all-layer/KV-head event
coverage before cross-workload execution semantics. This provenance guard does
not change Route-A policy/state/attention or create a timing/hardware claim.

A4154 can additionally bind the same collector/A4151 cross-workload coverage
before elision semantics. This prevents reuse of a merely parameter-matching
certificate with a different source and remains provenance-only.

### A4.1.7.10 implementation — second-workload paired elision measurement

The second-workload A4155 paired measurement requires
`--require-cross-workload-source-coverage`. It rejects an A4154 certificate
unless its relay binds the exact current event-file SHA-256 and the exact
all-layer/KV-head coverage and event count certified through A4151. The result
remains a repeated, fixed-request Python-reference attribution between
unelided and empty-source-elided Route-A only; it is not a Full-KV comparison,
same-mask-dense comparison, HBM result, throughput result, or hardware claim.

### A4.1.7.12 implementation — second-workload three-path profiler

A4163 is deliberately not another timing run. It binds the completed A4162
three-path measurement and A4151/A4154 provenance, then captures one separate
profile per Full-KV bypass, same-mask dense replay, and empty-source-elided
Route-A path after a fresh unprofiled warm-up. Its Route-A labels require each
hot/pending/packed source to be either a partial call or an empty skip for
every merge. Nested profiler ranges can localize Python-reference work but are
not latency, HBM, throughput, hardware, or RTL evidence.

### A4.1.7.13 implementation — component-accounting report

A4164 is a no-model provenance-bound report over A4161/A4162/A4163. It checks
their common replay event identity and prerequisite guards, then reports the
fixed-request source partial/skip/merge structure normalized by reported
generated tokens alongside the already measured reset-run medians. It never
sums profiler ranges and does not convert software calls into hardware traffic
or latency.

### A4.1.7.14 implementation — fresh long-horizon semantic pipeline

A4165 creates one new output root and executes a new online dense replay
source, A4151 execution-only semantic certification, and A4154 elision
semantic certification at an all-layer/all-head horizon of at least 32 tokens.
It binds their source identity and reports page/state plus source
partial/skip/merge structure. It is deliberately untimed; repeated three-path
measurement follows only if this semantic pipeline completes.

### A4.1.7.15 implementation — long-horizon three-path measurement

A4166 accepts only a completed A4165 long-horizon pipeline, then invokes the
existing certified A4162 three-path runner in a child directory. The parent
binds the fresh source SHA to the child manifest. It is the first long-horizon
repeated software distribution after semantic acceptance; it remains neither
HBM nor hardware/RTL evidence.

### A4.1.7.16 implementation — long-horizon three-path profiler

A4167 accepts only a completed A4166 parent and its bound all-layer/all-head,
budget-512, 32-token-or-longer A4165 semantic pipeline. It invokes A4163 in a
new child directory, with cached-model offline resolution, for one separated
profiler capture after the child’s own fresh warm-up per Full-KV bypass,
same-mask dense replay, and empty-source-elided Route-A path. The parent binds
the source SHA and requires the child’s token-digest, source partial-or-skip
versus merge, and coalesced-phase guards. Its output is diagnostic attribution
only and must not be interpreted as a timing distribution, HBM/traffic,
throughput, hardware, or RTL result.

### A4.1.7.17 implementation — cross-horizon accounting report

A4168 is a no-model report over the completed 16-token A4164 report and the
32-token A4167 profiler parent. It first validates each horizon's own internal
source/semantic/execution/profiler relation, then normalizes hot, packed and
pending partial-or-skip calls plus merge calls by the recorded generated-token
count and includes the independent page/tail witnesses. Fresh source SHA-256
identity is intentionally not required across horizons and is reported, rather
than concealed. It does not carry forward or compare profiler range time as
latency and does not make a hardware, HBM, traffic, or RTL claim.

### A4.2.0 implementation — observed resource/interface contract

A4200 consumes A4168 and its bound A4167 parent, rechecks all-layer/all-head
external storage, replay consumption, native-cold absence, pending-skip and
page/tail evidence, then records the software-observed control/data-plane
interface: bypass versus fast-path selection; ordered hot, pending and sealed
packed sources; and exactly one online-softmax merge decision per attention
evaluation. It explicitly lists unresolved FIFO/overflow, page-table/allocator,
bank/burst/gather, merge precision/scheduler, and switching/service parameters.
It is a contract input for later sensitivity work, not an architecture spec,
hardware sizing decision, or RTL authorization.

### A4.2.1 implementation — contract sensitivity matrix

A4201 binds each unresolved A4200 field to its A4 observed interface statement
and to the corresponding declared A3.6/A3-edge sensitivity range when one
exists. FIFO capacity/overflow, metadata, pending gather/burst, merge state,
and admission-engine/control ranges remain candidate model axes only. In
particular, A3-edge keeps a KV head-group on one engine and models no
cross-engine merge, while A4 validates a logical three-source online merge;
the matrix records this as a reconciliation obligation rather than pretending
that either source chooses the final scheduler. It is no-model contract
bookkeeping and neither hardware sizing nor RTL authorization.

## Current A4 handoff — 2026-09-09

The completed state is: A4.0 same-mask packed/pending/hot semantic guards;
A4.1 all-layer/all-head Qwen3-8B fixed-request software functional and
profiler evidence; A4168 h16/h32 source/page accounting; A4200 observed
resource/interface contract; and A4201 mapping of all unresolved fields to
declared A3 sensitivity axes. A4201 did not choose any hardware value.

The next bounded task is **A4.2.2 scheduler/merge placement reconciliation**.
It must compare, as a new explicitly modeled contract study, at least:

- co-located `(layer, KV head-group)` hot/pending/packed source service and
  merge, preserving the A3-edge no-cross-engine-merge placement; and
- split-source service with an explicitly represented partial-softmax reduction
  state/interface.

Inputs must include A4200/A4201 by hash and retain their policy point
(`threshold=-4`, hot window 128, page 64, budget 512). The output must not
claim a selected PE count, bandwidth, latency, HBM traffic, energy, area,
hardware acceleration, RTL readiness, or cross-model result. The new-conversation
brief is `analysis/route_a_a4_discussion_brief_20260909.md`.

### A4.2.2 implementation — scheduler/merge placement reconciliation

A422 is a fresh, no-model **modeled** contract comparison bound by SHA-256 to
A4168 source partial/skip/merge accounting, A4200's observed interface, and
A4201's declared candidate ranges. It retains the Qwen3-8B observation point
(`threshold=-4`, window `128`, page `64`, budget `512`) and requires per-source
decision conservation. Co-located service keeps hot, pending, packed, and the
one logical online merge inside a single `(layer, KV head-group)` engine,
preserving the A3-edge no-cross-engine-merge assumption. Split-source service
instead exports `{partial max, normalization state, value accumulator,
valid/empty}` from every non-empty source to an explicit reduction interface.
Its transfer/dispatch/state-capacity grid is abstract modeled interface work,
not a timing schedule; without service timing it cannot infer a reduction FIFO
occupancy or select any implementation parameter. A422 does not establish HBM
traffic, hardware latency/throughput/energy/area/frequency, acceleration, RTL
readiness, or a final placement choice.

### A4.2.3 implementation — marginal fan-in/service sensitivity

A423 binds A4168 and A422 by SHA-256 and keeps its result explicitly
**modeled**. The accepted accounting has source marginals but no source-service
or reduction-arrival timeline. A423 therefore uses inclusion-exclusion to bound
the number of evaluations with 1/2/3 active sources, then sweeps abstract
co-located serial service versus split-source barrier service. Its capacity
axis is only a per-logical-evaluation state sensitivity label, not measured
queue occupancy, a physical FIFO depth, a reducer count, or timing. The report
does not select a placement or hardware parameter and establishes neither HBM
traffic nor latency/throughput/energy/area/frequency, acceleration, or RTL
readiness. Ordered source/reduction events are required before a later study
can make queue or placement-performance claims.

### A4.2.4 implementation — ordered logical source/merge event gate

A424 adds an explicit-off-by-default logical recorder to the policy-on
external-cold state. Its event records global invocation order, layer, KV/query
head, cache position, ordered hot/pending/packed partial-or-skip outcomes,
scalar source position ranges, page/tail witnesses, and the merge marker. It
records no Python/CUDA/hardware timestamps or source/reducer completion events.
Trace-off versus trace-on forced/independent runs retain the original mask,
replay, external ownership, native-cold-absence, source-decision, token and
logit checks. The resulting gzip JSONL enables a later declared-work schedule
model but is neither an observed queue/backpressure trace nor hardware timing,
HBM, throughput, energy, area, acceleration, or RTL evidence.

### A4.1.7.11 implementation — second-workload three-path measurement

A4162 closes the immediate cross-workload baseline gap with repeated fresh
reset runs of Full-KV bypass, same-mask dense replay, and A4154-certified
empty-source-elided Route-A external storage. It verifies the current A4151
and A4154 certificates and their source-coverage relay before timing. Dense
and Route-A each require their certified token digest; their equality is
recorded rather than assumed, while Full-KV equality is neither a mask nor a
generation requirement. The resulting CUDA/wall and allocator distributions
are fixed-request Python-reference measurements only, never HBM, throughput,
hardware, or RTL evidence.

### A4.2.5 implementation — ordered logical dependency schedule sensitivity

A425 consumes the completed A424 timestamp-free logical event stream and
completed A422/A423 reports by SHA-256, while retaining the same Qwen3-8B
policy point. It verifies a contiguous global invocation sequence, ordered
hot/pending/packed partial-or-skip outcomes, and exactly one merge marker per
event. It then evaluates declared virtual-work sensitivity rows for co-located
logical `(layer, KV head)` source-plus-merge ownership and split-source
partial-state exports to a local reduction dependency. Logical submission
spacing, source, transfer, dispatch, and merge work are assumptions, and its
work positions/dependency waits are not timestamps, cycles, latency, queue
occupancy, FIFO depth, service/completion order, controller timing, HBM
traffic, throughput, energy, area, hardware sizing, a final placement, or RTL
evidence.

### A4.2.6 implementation — exact logical fan-in accounting

A426 consumes A424's accepted timestamp-free gzip event stream and A423 by
SHA-256. It verifies A424's independent-run source accounting before deriving
exact 1/2/3-active-source and source-combination counts, including per-layer/
KV-head rows, and checks them against A423's marginal inclusion-exclusion
bounds. It closes only the one-request fan-in overlap ambiguity; it adds no
source service/completion order, reduction arrival, queue/FIFO occupancy,
engine utilization, cycles, latency, throughput, HBM traffic, energy, area,
hardware sizing, scheduler choice, or RTL evidence.

### A4.2.7 implementation — cross-workload logical-event stability

A427 creates a fresh retrieval replay source and independently passes A4151,
A4154, and A424 all-layer/all-KV-head semantic/event gates before comparing it
with the accepted summarization A424 event artifact. It reports only source
partial/skip, exact fan-in, and source-combination fraction deltas at the same
declared non-horizon policy point, while preserving distinct source hashes and
recording both declared caps and actual policy-decode-call counts. A long-cap
probe chooses the semantic child cap; the separately collected semantic source
can have fewer `q_len=1` calls because of multi-token question forwarding or
EOS. A4151/A4154/A424 replay-complete gates, rather than the wrapper, verify
exact source consumption. It deliberately
does not pre-register or select a stability threshold. Its event-structure
comparison cannot establish source service/completion or arrival order, queue/
FIFO occupancy, backpressure, cycles, latency, throughput, HBM traffic,
energy, area, hardware sizing, scheduler placement, or RTL readiness.

### A4.2.9 implementation — matched split-source interface demand

A429 consumes A428's matched-call event artifacts and A422's explicit
co-located/split interface contract by hash. It counts a modeled split export
for each nonempty logical source and extra reduction inputs beyond the first,
with per-workload and per-layer/KV-head record/page/tail distributions.
Co-located exports remain explicitly zero. These are not state bytes, service
times, queue/FIFO occupancy, hardware scheduling, or RTL evidence.

### A4.2.10 implementation — modeled scheduler/backpressure envelope

A4.2.10 consumes A428/A429/A425 by hash and applies declared virtual source
and reducer work profiles to the timestamp-free event submission order. It
reports split-source abstract in-flight state and blocking sensitivity alongside
zero co-located cross-engine exports. No source arrival/completion observation,
FIFO depth, physical scheduler, latency, throughput, or hardware conclusion is
made.

### A4.2.11 implementation — partition and burst sensitivity

A4211 uses A428/A429 hash-bound events to sweep declared reducer placement,
logical cache-position bursts, fan-in merge hierarchy, parallelism and abstract
task capacity. It separates global from local ownership assumptions but does
not observe arrival/completion time or select hardware resources.

The revised v2 contract treats all active partials of one logical invocation
as one fan-in merge task. Its abstract buffer holds merge tasks, avoiding the
rejected v1 assumption that a reducer serially consumes every partial state.
The preserved v1 output is not used to size a FIFO.

### A4.2.12 implementation — source-ready/dispatch dependency evidence

A4212 derives a fresh, hash-bound dispatch-epoch artifact from the accepted
three-workload A428 event streams. It does not alter mask replay, append,
attention, or merge semantics and executes no model. The artifact retains the
actual Python-reference logical invocation order, identifies forward epochs
from layer-order resets, and identifies a layer dispatch epoch from each
contiguous `(layer, phase, cache_position)` region. It verifies that each
same-layer/KV-head group saw a consistent hot/pending/packed source snapshot.
That is a functional/dependency boundary: same-layer query-head partials may
be modeled as ready together after append, whereas cross-layer events remain
ordered. It is not source completion timing, concurrent Python execution,
hardware dispatch, queue/FIFO occupancy, latency, throughput, HBM, or RTL
evidence.

A4211 schema v2 binds A4212 by SHA-256 and adds the explicit
`trace_dispatch_epoch` modeled arrival contract. It removes the unjustified
choice between a fully global sequential stream and a cache-position-wide
burst, but still cannot select a reducer placement or any resource size.

### A4.2.13 implementation — same-layer group sharing boundary

A4213 uses the A4212 dispatch epochs to verify that the four query heads in
each Qwen KV head-group see one identical hot/pending/packed source and page
snapshot. It therefore permits one logical source/page-descriptor dispatch
control per active source per group, instead of repeating that control once
per query head. It explicitly does **not** coalesce Q-dependent partial
attention, partial-softmax state, or online merge: every query head still
owns those results. Its reported control-unit reduction is a logical contract
count, not an operation, byte, traffic, time, queue/FIFO, throughput, or
hardware benefit.

### A4.2.14 implementation — Qwen anchor closure

A4214 closes the current Qwen3-8B/KVzap A4.2 anchor without freezing an
architecture. It verifies all required upstream guards and hashes, then emits
three deliberately separate sections: Route-A Core Contract v1; the three
fixed-workload Qwen resource descriptor; and portability preconditions plus
explicit non-claims. The Qwen `group_width=4`, fan-in/page/tail distributions,
and logical dispatch-control accounting remain model/workload descriptors.
A4201 hardware fields remain unresolved and A4211 placement/arrival studies
remain modeled sensitivity only. The next research scope is a minimal second
KVzap-model portability gate, not further Qwen micro-sensitivity or RTL.

### M0 implementation — Nous Llama 3.1 8B provenance and structural eligibility

The first second-model gate is intentionally no-model. The M0 validator checks
the cached fixed-revision Nous snapshot, safetensors index/shard presence,
Llama JSON structural fields, the `KVzapPress`-derived Linear predictor ID,
the official candidate predictor ID, and the resolved predictor JSON dimensions.
If the two IDs differ, the manifest is `blocked` until the invocation explicitly
binds the separately reviewed default-off `predictor_repo_id_override` to the
official candidate. It cannot establish equivalence, mask behavior, lifecycle,
performance, hardware, or RTL conclusions; those remain M1+ work.

### M1 implementation — Nous Llama 3.1 8B semantic portability

M1 is intentionally a narrow functional integration gate, not a second-model
rerun of Qwen A0--A4.  The new runner hash-binds completed M0 provenance and
requires the reviewed explicit, default-off Linear predictor override because
the Nous repository basename cannot derive the official predictor name.  It
does not instantiate `DMSPress` or the fake-key path.  Instead it runs one
fixed request as Full-KV bypass, online same-mask dense control, and replayed-
mask Route-A hot/pending/packed control over all 32 layers and all 8 KV heads.
The dense control provides one online original-mask stream; Route-A must consume
every event exactly once rather than independently re-score after its own
attention substitution can alter later hidden states. Every selected group also receives the existing same-mask FP32 and
executed-dtype attention guard.  Page/admission values are explicit reference
inputs only, and source-state witnesses are reported rather than assumed.  A
passing M1 supports semantic portability for this exact model/predictor/request
contract.  It does not prove accuracy, broad model portability, lifecycle or
resource-envelope stability, HBM/latency/throughput/energy/area, hardware
parameter selection, architecture specification, or RTL readiness.

### M2 implementation — Nous Llama 3.1 8B lifecycle portability

M2 adds only the next missing semantic layer: whether the M1-compatible mask
stream evolves through the Route-A lifecycle on this model. It binds M0/M1
hashes and runs all layers/all KV heads at two explicit reference points.
Budget one must expose hot, pending, and packed sources; budget 512 must expose
a sealed full page, multi-page state, and a nonempty packed tail. The dense pass
remains the only online score source, while Route-A replays its mask exactly
once and retains same-mask numerical guards. Route-A state conservation and
contiguous-position assertions are exercised, but this gate does not
replace/free Llama's native cache. It supports fixed-request functional/
trace-derived lifecycle portability only, not physical memory, traffic, timing,
general workload behavior, hardware parameter selection, or RTL readiness.

### M3 implementation — Qwen/Llama portability closure and separate descriptors

M3 is deliberately a no-model archive comparison rather than another model
run. It hash-binds the Qwen A4.2.14 closure and the completed Nous Llama M0,
M1, and M2 chain, rejecting incomplete guards or a broken M0/M1/M2 provenance
link. A successful report says only that two fixed model/predictor/request
anchors cover the Route-A same-mask/Full-KV-bypass semantics and the
hot/pending/packed lifecycle state classes. It keeps Qwen's three fixed
workload source/fan-in/page-tail descriptor and Llama's one-request lifecycle
state summaries explicitly separate. Neither descriptor is a universal
resource range, accelerator dimension, performance observation, architecture
specification, or RTL authorization.

### M3.2 archival clarification — descriptor units and source reconciliation

M3.2 is a new-output correction to archive expression, not an additional
experiment. It binds the completed M3.1 report and labels `kv_heads_per_layer`
separately from `total_layer_kv_head_state_count`: Qwen is 36 x 8 = 288 and
Llama is 32 x 8 = 256. If hosts hold different raw A4.2.14 Qwen report bytes,
M3.2 records that fact and compares the canonical projection of all Qwen fields
that M3.1 serialized or consumed. A matching projection supports the existing
M3 semantic conclusion only; it does not prove source-file byte identity, add
a workload, establish a common hardware envelope, or alter RTL readiness.

### M4 implementation — bounded Llama workload descriptors

M4 does not reopen Qwen A0--A4. It retains the completed retrieval M2 anchor,
then applies the unchanged M2 same-mask dense/replay lifecycle gate once to
each fixed built-in summarization and reasoning request. A no-model aggregator
hash-binds all three M2 manifests and rejects any differing M0/M1 provenance,
functional inputs, duplicate request content, or missing lifecycle guards. It
reports each request's source presence, page witness, exact-mask decision
count, and bounded final-state scalars independently. This is only a three
request Llama coverage matrix; it is neither an accuracy test nor a resource
distribution, physical-capacity/traffic/timing result, hardware choice, or RTL
gate.

The first strict M4 summarization attempt preserved a started-only directory
after an execution-dtype ULP breach (33 versus the default 16) during Route-A
replay. The failure is evidence, not a reason to silently relax the guard. The
M2 runner therefore exposes a default-preserving `record_only` ULP diagnostic
mode with bounded scalar samples. It leaves FP32/executed-dtype guard work and
exact dense-mask replay active, but records the breach as non-strict evidence.
M4 reruns all three inputs in fresh, mode-matched directories rather than
mixing strict retrieval with record-only workloads.

### M4.1 implementation — bounded summarization ULP diagnosis

M4.1 is a no-model diagnosis of the retained M4 record-only summaries, not a
rerun or relaxed strict gate. It binds the M4 report and three M2 inputs, then
reports each summarization breach alongside FP32 absolute difference, local
values, ULP spacing, reference point, and location multiplicity. The fixed
retrieval/reasoning zero-breach rows provide only comparator context. Even if
all sampled FP32 maxima are below the declared `atol`, M4.1 must retain the
strict-ULP failure and cannot select a merge precision, hardware resource, or
RTL direction.

### M5 implementation — matched-horizon Llama descriptor alignment

M5 closes the specific descriptor gap left by M4: M4 had source presence and
final state scalars, but not the per-attention source-combination/fan-in and
page/tail distributions required for field-level comparison with Qwen A4.2.8.
It hash-binds completed M0, M1, M4, and M4.1 reports. The M4.1 record-only
summarization context stays explicit: M5 cannot present its run as a strict
16-ULP pass. Under the same fixed eight-token cap, each Llama built-in request
uses a separate Full-KV bypass, online same-mask dense mask source, and
Route-A exact replay. The replay enables the existing untimed logical recorder
and must retain all-layer/all-KV-head, replay-complete, numerical-guard-work,
hot/packed, source-decision partition, and equal actual decode-call guards.

The output records only hash-bound, normalized source-combination, active
fan-in, partial record-count, and page/tail descriptor rows, including
`(layer, KV head)` rows. This is functional/trace-derived evidence with no
source-ready or completion timestamp. It aligns the descriptor schema with
Qwen; it does not demonstrate equal distributions, a common resource envelope,
source overlap, scheduler/backpressure behavior, FIFO occupancy, capacity,
HBM traffic, timing, throughput, energy, area, a hardware parameter, an
architecture specification, or RTL readiness.

### M5.1 implementation — fixed-horizon correction after preserved M5 failure

M5's `_01` output is deliberately retained as a started-only failed attempt:
the shared `max_new_tokens=8` cap produced six Llama `q_len=1` calls for
retrieval and seven for summarization/reasoning. The per-request gzip files
remain evidence of that mismatch but are not an accepted matched-horizon
descriptor. M5.1 does not overwrite them. It hash-binds the failed started
record and M0/M1/M4/M4.1 provenance, then writes a new output using an explicit
non-EOS fixed eight-token continuation. Each path executes the same number of
forwards; dense produces the fixed token trajectory and original mask stream,
and Route-A must replay both. M5.1.0's extra whole-vocabulary logits-close
check is retained as a failed started-only attempt, not weakened in place.
M5.1 schema v1.1 instead retains the established per-attention same-mask
FP32/executed-dtype guards; a whole-model logits equality after deliberately
forcing post-EOS tokens is not part of the M1/M2 semantic contract.

The successful M5.1 contract requires seven `q_len=1` calls across every layer
and all three workloads, with the same existing all-layer/all-KV-head,
replay-complete, numerical-guard-work, source partition, and timestamp-free
event guards. It is a conditioned functional/trace-derived descriptor study,
not a natural-generation experiment. No resulting descriptor establishes
quality, source-ready/complete timing, concurrent overlap, scheduler or
backpressure behavior, queue/FIFO occupancy, cycles, HBM traffic, throughput,
energy, area, hardware resources, architecture specification, or RTL
readiness. M4.1's record-only summarization ULP status remains explicit.

### A4.2.8 implementation — matched-horizon three-workload stability

A428 collects fresh summarization, retrieval, and reasoning sources under one
declared cap, rejects the run unless their actual all-layer policy-decode-call
counts match, then independently requires A4151, A4154, and A424 for each.
The timestamp-free result records hashes and compares fan-in, source
combinations, partial record counts, and packed page/tail witnesses. It removes
the A427 horizon mismatch but remains three fixed-request logical-event and
functional evidence, not a workload distribution, timing trace, queue/FIFO or
backpressure observation, hardware result, scheduler choice, or RTL evidence.

### M6 implementation — conditioned cross-model descriptor coverage

M6 is a no-model, new-output closeout step after the accepted Llama M5.1
fixed-horizon study. It hash-binds the completed Qwen A4.2.14 closure and
A4.2.8 matched-horizon descriptor reports with the Llama M5.1 descriptor
report. It additionally binds M3.2 to reconcile the known cross-host raw Qwen
A4.2.14 JSON-hash difference through its canonical consumed projection and two
registered raw hashes; an unreconciled or unrecognized difference rejects the
run. The gate requires both anchors'
completed semantic/event guards, a
shared declared eight-token continuation, seven actual all-layer `q_len=1`
calls, hot window 128, and page reference 64. It preserves all six fixed
model/workload rows and compares only normalized source combinations, fan-in,
active source presence, source-nonempty conditional record-count quantiles, and
packed-tail quantiles.

The resulting min/max values are an observed fixed-row *coverage envelope*: a
planning input for later workload expansion, not a hardware resource range. In
particular, M6 must not pool Qwen/Llama absolute event counts, layer counts, or
aggregate layer-head counts, and it selects no FIFO, PTE, bank/burst, merge
precision, PE count, scheduler, controller timing, capacity, traffic, latency,
throughput, energy, area, architecture specification, or RTL implementation.
Llama's M4.1 strict-ULP non-pass remains record-only context, not a precision
decision.

### P0 implementation — SnapKV terminal frontend contract

The first non-KVzap frontend is deliberately a narrow admission gate, not a
claim that Route-A already supports arbitrary pruning algorithms.  SnapKV on
the frozen Qwen3-8B model is prefill-only: after dense prefill it scores and
top-k selects a final KV set.  `SnapKVPress` normally gathers the selected K/V
in score-ranked order and replaces the native cache; that mutation path is not
used by P0.

`kvpress.route_a_frontend_contract.SnapKVPrefillDecisionObserver` attaches a
read-only post-attention observer, obtains the same score tensor and native
`ScorerPress.select_topk_indices` selected set, and writes one terminal
decision per `(layer, KV head, original position)`.  The new
`route-a-frontend-decision-stream-1.0` retains declared sequence length, so
the validator rejects a missing tail rather than accepting a falsely shortened
stream.  It also rejects duplicate identities, non-finite scores,
non-contiguous position coverage, incorrect keep count, and any dropped
position in SnapKV's observation window.  This records an immutable
`prefill_terminal` action set in canonical original-position order; it does
not reinterpret score-ranked native gather order as Route-A state order.  Its
two dense passes share a seed and require equal trace-off/observer answer
digests before an artifact can be written.

P0 proves only that a collected SnapKV selection can meet the frontend
finality/identity/replay prerequisites.  It supplies no online maturity or
pending-state evidence, no native cache/decode equivalence, and no quality,
physical capacity, traffic, timing, scheduler, hardware, architecture, or RTL
result.  The cross-frontend sequence is P1 then P3 then P2: P1 records the
offline packed-page opportunity of this fixed terminal stream; P3 subsequently
replays it in a bounded same-mask dense versus Route-A functional reference;
P2 is deferred until that mapping is accepted.  Existing KVzap artifacts,
defaults, and frozen traces remain unchanged.

### P1 implementation — SnapKV terminal-stream packed opportunity

P1 is deliberately an A0-shaped static analysis, not a reuse of the completed
KVzap A0 numeric result. `tools/analyze_snapkv_route_a_p1_packed_opportunity.py`
hash-binds and revalidates one completed SnapKV P0 manifest and its terminal
decision NPZ, including the trace-off/on observer guard. It reconstructs a
complete final keep/drop array only after rejecting missing identities,
noncontiguous layer/head IDs, multiple calls, or a hash mismatch.

For the initial mapping, SnapKV's P0-protected observation suffix is the only
resident hot window; each earlier retained `(layer, KV head, original position)`
record appends to its own cold page list and drops are absent. This is a
declared compatibility mapping, not a frozen Route-A hot-window or hardware
choice. P1 sweeps page sizes and reports slots/pages/tail plus explicitly
declared metadata/K+V accounting. It contains no model execution, same-mask
functional proof, admission/pending trace, allocator/HBM measurement,
scheduler/timing evidence, or hardware/RTL result. P3 is still required before
any lifecycle/resource descriptor study.

The accepted fixed-request P1 output is
`analysis/experiments/snapkv_route_a_p1_packed_opportunity_qwen3_8b_01/`
with report SHA-256
`f55f4a4ca9020dcbf02acce3c7f272dfafd5ecfd0bdfb2a79918015ddfd3010d`.
It binds P0 manifest `c4a2ef3150197cab46508445f03c622238d93cd650b2778e5981d3b9a0927599`
and stream `1cb4a7bba15e54486b85cf0377554b5384999e11703183550bdc6809b1e7a365`.
All 288 layer-head streams have the same 891/445 total/keep count: the P0
64-token protected suffix is hot, 381 earlier keeps are cold, and three cold
tail slots round to 384. Hence P=16/32/64/128 changes only the static per-head
page count (24/12/6/3) and declared metadata; every row has 129,024 physical
slots, 128,160 ideal slots, and 1.98884x fixed-request full-to-physical slot
factor. It does not select a page size or establish a wider distribution.

### P3 implementation — SnapKV same-mask prefill-tail semantic gate

P3 bridges the completed P0 terminal stream and P1 static mapping to bounded
Route-A attention semantics. The runner recomputes and cross-validates P0/P1
SHA-256 provenance, P1's P0 back-pointers, original-position cold mapping, and
the P1 P=64 row before consuming each `(layer, KV head, original position,
keep, score)` decision exactly once. Native score-ranked SnapKV gather order
is excluded.

P3 has no legitimate source decision beyond P0 context prefill. It runs that
prefill only, leaves its multi-token attention output unchanged, then probes
the final actual prefill query against independent same-mask dense and Route-A
hot/pending/packed plus online-softmax states. It records scalar numerical and
state evidence only. `page_tokens=64` and `admission_budget=4096` materialize
P1's terminal P=64 state for this functional check; they select no FIFO, PTE,
bank/burst, merge precision, PE, scheduler, controller, or hardware setting.

FP32 same-mask comparison remains enforced; executed-dtype ULP is explicitly a
bounded record-only rounding diagnostic, never a strict ULP pass or a
merge-precision selection.

P3 is trace-derived at its terminal mask and functional at its same-mask
comparison. It cannot establish native SnapKV decode/cache behavior, quality,
allocator/physical capacity, HBM traffic, timing, scheduling/backpressure,
throughput, energy, area, architecture specification, or RTL readiness.

### P2 implementation — SnapKV lifecycle/resource descriptor

P2 closes the narrow frontend branch's evidence accounting after P0 -> P1 ->
P3.  `tools/analyze_snapkv_route_a_p2_lifecycle_resource_descriptor.py` is a
no-model, new-output tool.  It verifies P0/P1/P3 SHA-256 provenance and rejects
a P3 manifest without the accepted terminal replay, P1 P=64 state,
same-mask-FP32, canonical-order, and no-native-SnapKV-cache-replacement
guards.

It records the small set of available fields (terminal action, identity/order,
protected-suffix compatibility mapping, static terminal packing, and bounded
prefill same-mask semantics) separately from explicitly unavailable fields.
The latter include online maturity and pending lifecycle, generated-token
continuation, native cache/decode behavior, source-ready/dispatch/completion
ordering, scheduler/backpressure, allocator/interface state, and hardware
metrics.  Missing evidence is `null` and is never silently treated as a zero
queue, source, traffic, or resource value.  Therefore P3's zero-pending final
state is not a decode-pending conclusion.

P2 is a provenance-backed trace-derived/functional classification, not a
hardware model or measurement.  It cannot select hardware parameters or support
native SnapKV decode, scheduling, traffic, latency, throughput, energy, area,
architecture, or RTL claims.

The completed Qwen3-8B fixed-request report is
`analysis/experiments/snapkv_route_a_p2_lifecycle_resource_descriptor_qwen3_8b_01/`
with SHA-256
`29835a960c9a010421bf088ad3a869c476f5c67041b0127e4395df41a7c1aa29`.  It
hash-binds the accepted P0 manifest/stream, P1 report, and P3 manifest:
`c4a2ef3150197cab46508445f03c622238d93cd650b2778e5981d3b9a0927599`,
`1cb4a7bba15e54486b85cf0377554b5384999e11703183550bdc6809b1e7a365`,
`f55f4a4ca9020dcbf02acce3c7f272dfafd5ecfd0bdfb2a79918015ddfd3010d`, and
`56cd9ca61d303be0154ec12c2934ee4b71c08332d8dc8d32c5e09ca27c73ff37`.
The descriptor classifies five fields as available and eight as unavailable for
the 256,608-action one-shot prefill stream; P3 deliberately issued zero
generated-token forwards.  It therefore closes only static canonical mapping
and bounded prefill semantic portability.  Decode lifecycle/pending, native
cache/decode, scheduler/backpressure, and physical-resource/hardware
portability remain unsupported, rather than being treated as zero-cost or
zero-occupancy behavior.

### DMS-M0 implementation — official trained-DMS entry gate

The next frontend is the official trained `nvidia/Qwen3-8B-DMS-8x` checkpoint,
not the existing KVPress DMS-like wrapper.  The checkpoint supplies custom
configuration, model, attention, and cache code, so
`tools/validate_dms_m0_official_provenance.py` first hash-binds its pinned
snapshot revision `da1535fc3bfb52fa340eca692a7e4e650f98838d`, expected DMS
8x/512-window configuration, code files, Safetensors index, and shard headers
without executing custom code or materializing weights.

Its explicit runtime modes then permit only a config load or one short
cache-enabled prefill from the local snapshot.  They do not generate, mutate
KVPress, implement a Route-A adapter, collect a DMS lifecycle trace, or make a
quality/hardware claim.  A failed compatibility attempt must be retained as a
fresh blocked manifest and must not be hidden by falling back to `DMSPress` or
a different model/runtime.  M1 starts only if the exact official source and
runtime probe are accepted.

#### DMS-M0 recorded result — source gate accepted, runtime probe blocked

The fresh remote result
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_01/` has
manifest SHA-256
`a8b6099eaa618249ff49ef73c43fb7a8df55d2aca2eb510f8c3cd922835b655e`.
Static source checks all accepted: the fixed official revision's expected
DMS-8x/512 Qwen3 fields, four indexed Safetensors headers, and four parseable
custom-code files.  That static phase did not execute checkpoint code or
materialize any weight tensor.

Its deliberately bounded `model-prefill` compatibility probe imported the
pinned configuration code, but model-code import raised
`ModuleNotFoundError: No module named 'flash_attn'` in the existing PyTorch
`2.10.0+cu128` / Transformers `5.0.0` environment.  It therefore records
`model_weights_loaded=false` and `generation_calls=0`: no weights, prefill,
generation, DMS lifecycle evidence, Route-A adaptation, quality result, or
hardware observation exists.  This is an environment dependency blocker only;
it neither rejects the official checkpoint nor licenses a `DMSPress` fallback.
M1 remains gated on a separately recorded successful exact-source probe in an
explicitly approved compatible isolated runtime.

An existing isolated `debug_env` was then checked without environment changes.
It provides FlashAttention `2.8.3` with PyTorch `2.5.1+cu121`, but its
Transformers `4.52.4` runtime is still incompatible.  The no-model static
result completed in
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_debug_env_static_01/`
(manifest SHA-256
`a77bee5d89f36889a548a5c9dcd77f7dac4a5a173362eccf1efc3243a945b861`).
The separate prefill probe in
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_debug_env_01/`
is blocked before custom checkpoint code/weight loading with
`ImportError` for `layer_type_validation` from
`transformers.configuration_utils` (manifest SHA-256
`91ac04a5d90b11090fc14cce9a325023fe35999f869d312e677c541738336f8e`).
This resolves neither DMS semantics nor Route-A; it only establishes that a
usable runtime must meet both the custom-code Transformers API and the
FlashAttention binary dependency together.

The unified KVPress `.venv` then passed a separate FlashAttention dependency
gate: the hash-pinned third-party
`flash_attn-2.8.3.post1+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64`
wheel (SHA-256
`35e46afd97efbbc9a1163ddf7f8acb7f32a95927ca02b0bd323a14de740c303f`)
installed with no dependencies, while PyTorch remained `2.10.0+cu128`.  A
minimal A100 `sm_80` CUDA call passed; it is a software dependency function
check only, not a hardware performance observation.

The subsequent fresh M0 result is
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_venv_flash_attn_01/`
with manifest SHA-256
`d39a15f0aadbdfefc07665361d8fca8dbd449b179c6095c0ab53129565cfc125`.
It has passed the missing-FlashAttention point and imported the pinned
configuration custom code, but it is blocked before weight loading/prefill by
`AttributeError: 'Qwen3Config' object has no attribute 'pad_token_id'` in
Transformers `5.0.0`.  It records zero generation calls.  Thus this is the
next exact environment API blocker, not an official DMS or Route-A negative;
M1 remains gated.

#### DMS-M0 recorded result — compatible `debug_env` runtime accepted

The official DMS README requires Transformers `4.57.3` and explicitly obtains
the tokenizer from base `Qwen/Qwen3-8B`; its DMS snapshot does not include
tokenizer files. The M0 tool now makes that second input explicit through a
local-only `--tokenizer-root` and hash-records selected tokenizer files. Only
the isolated `debug_env` was changed: Transformers became `4.57.3`, while
PyTorch stayed `2.5.1+cu121` and FlashAttention stayed `2.8.3`.

After a new-output static gate (manifest SHA-256
`35f65e8e72b2342bc4e1caa76157792e6932cbe93c07501798aca9ac384633a7`), the
fresh prefill result at
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_debug_env_tf457_base_tokenizer_prefill_01/`
completed with manifest SHA-256
`0fda714d8f67b9c646c82788113b4e037c9e3b70ef12121b6133cb103dc7687d`.
It loaded the official DMS weights and completed one cache-enabled seven-token
prefill with finite logits; `generation_calls=0`. This removes the runtime
blocker for the exact recorded inputs, but is only functional compatibility.
It does not validate DMS pruning/mask semantics, Route-A behavior, accuracy,
decode lifecycle, traffic, timing, hardware, or RTL. The next work is a
separate DMS-M1 semantic gate, not hardware selection.

### DMS-M1 implementation and recorded result — native semantic observation

DMS-M1 is a separate narrow gate for the official trained-DMS frontend. It
does not substitute Route-A attention: the checkpoint's own source makes
binary decisions and its native cache delays eviction before reusing a slot.
The new observer only wraps inherited `DMSCache.update`; a normal official-DMS
run must exactly match the observed run's generated-token IDs, per-forward
last-logit digests, and final 36-by-8 cache-length digest. This excludes the
old KVPress `DMSPress`, KVzap, fake-key attention, and generation API.

The completed fresh result
`analysis/experiments/dms_route_a_m1_native_semantic_qwen3_8b_retrieval_02/`
has manifest SHA-256
`5c3e72957711c6d801667a2da0ca08720ce9e1238393b42137c1c9874a0aaa55` and
hash-binds the completed compatible M0 manifest. With a 625-token retrieval
input and four fixed decode forwards, it observes all 36 layers and 8 KV heads
on every one of five calls (180 events). It records 126,919 binary
decision-one bits; native cache length is below the 629-token logical history
in 269/288 layer-head states, with final length range 513--629. Observer
equivalence passed exactly. This is useful trace-derived/functional evidence
of DMS's native delayed-eviction-and-reuse lifecycle, but does not claim that
it already has a Route-A hot/pending/packed mapping, nor any physical capacity,
traffic, timing, hardware, or RTL result.

### DMS-M2 implementation — delayed-eviction and slot-reuse contract replay

The next DMS gate must preserve the distinction exposed by M1 rather than
forcing DMS into the KVzap packed-cold vocabulary. DMS-M2 therefore binds the
completed M0 and M1 manifest hashes, repeats the fixed official-DMS native pass
with trace-off/on equivalence, and captures only the official binary decision
stream plus structural event boundaries. It never records token IDs/text, K/V,
attention, logits, allocator data, or timing.

`tools/run_dms_route_a_m2_adapter_contract_gate.py` then feeds that stream to
an independent per-layer/KV-head pure-Python controller. The controller's
explicit modeled contract is delayed eviction: each bit labels the preceding
arrival; once that arrival reaches the configured ring candidate, its abstract
native slot is reused; otherwise cache length grows. It must reproduce every
official native pre/post cache-length vector and the final 36-by-8 matrix. The
model records that the official cache ring is one element larger than the
configured decision window; it does not silently choose a hardware FIFO depth.

M1's prior summary hash is recorded as a cross-run comparison only. It cannot
be an unconditional equality gate because M1 saved summaries rather than raw
decision bits and a later M2 run may use a different available GPU. M2 instead
binds identical request provenance and requires its own trace-off/on equality
and exact native-length agreement at every observed event.

The accepted M2 result is
`analysis/experiments/dms_route_a_m2_adapter_contract_qwen3_8b_retrieval_01/`,
manifest SHA-256
`52b1445bf591948c12b8af131e3c92be4be3a9c9f73f35804b5ff77d0cfc842e`.
On the M1-bound 625-token retrieval request plus four fixed decode forwards,
the capture contains 180 events and 127,047 decision-one bits. The independent
controller matched each official native cache-length transition and the final
36-by-8 matrix exactly. It found native shortening in 269/288 final
layer-heads and abstract slot reuse in 677 layer-head event states. The M1/M2
summary hashes differ across the separately run observations and are recorded
as such; they do not erase M2's within-run trace-off/on and controller guards.

If accepted, M2 provides trace-derived official DMS decision/cache observations
and a bounded functional controller replay for one request. It still is not a
Route-A hot/pending/packed-cold adapter, physical capacity/traffic measurement,
latency/throughput/energy/area evidence, trained-DMS quality result, architecture
specification, or RTL gate.

### DMS-M3 implementation — active native-slot topology precondition

M3 is not yet the Route-A mapping or an attention replacement. It binds M2's
compact decision artifact and runs the official DMS request with trace-off/on
equivalence while observing only `recent_info`, its cursor, decisions, and
native lengths. A separate controller augments the M2 delayed-eviction rule
with a logical arrival serial per source, and must reproduce native length plus
the complete ring metadata at every event. It exports the final logical source
serial for each active native slot, without K/V payloads or token IDs/text.

The purpose is to establish whether an adapter can represent DMS's actual
resident topology and whether native physical slot order differs from logical
arrival order after reuse. Passing M3 does not prove attention equivalence or
that those slots form KVzap-like hot/pending/packed-cold sources; any attention
replacement is a subsequent, separately guarded functional experiment.

The accepted M3 output is
`analysis/experiments/dms_route_a_m3_active_topology_qwen3_8b_retrieval_04/`,
manifest SHA-256
`f56816bb7998083de49ff24385f4bb5793d4445a98783c2063f328c2b3bf74a7`.
Its 180 events pass native cache-length, full ring metadata, and ring cursor
agreement; every final active slot has a unique logical source arrival. The
important result is that native physical slot traversal is nonmonotonic in
logical arrival order for 269/288 layer-heads (3,140 adjacent descents). The
controller reaches agreement only by reflecting the official software prefill
chunk rule: confirmed-eviction slots are filled before new slots. This is a
real adapter-control requirement, but not a hardware page/bank choice or proof
that external Route-A attention is equivalent.

### DMS-M4 — active-resident attention semantic gate (planned)

The next DMS gate is not a KVzap packed-cold substitution. It binds M0--M3 and
observes the official DMS decode FlashAttention call without changing it. A
temporary FP32 reference gathers only active native K/V slots in official
logical-slot/block-table order and compares its one-source online-softmax
output with the unchanged official output. Required guards are exact trace
off/on token/logit/final-cache state, fresh control/topology replay, all-layer
decode coverage, and explicit numerical tolerance.

If accepted, M4 proves one fixed-request functional active-resident attention
reference only. It does not show that evicted DMS K/V has a cold source, that
slots can be reordered, that sources can be split/merged, or that Route-A
scheduling, capacity, traffic, timing, hardware, quality, architecture
specification, or RTL follows.

### DMS-M4 result — native active-resident source is functionally replayable

The accepted run is
`analysis/experiments/dms_route_a_m4_active_resident_attention_qwen3_8b_retrieval_01/`,
manifest SHA-256
`6e4dc1eda065f440800ee29c03f65ad59502cf95c84f2408dce7ce8e6485b028`.
Its trace-off/on generated tokens, per-forward logits, and final native cache
digests are identical. For every one of 144 decode FlashAttention calls, the
temporary one-source FP32 replay over active K/V in official native logical-slot
order passes declared `atol=rtol=0.03`; recorded max absolute difference is
`0.0629558563` and mean per-call mean absolute difference is `0.0003103976`.

This makes the M3 order condition operational: the active native resident set
can be treated as one semantically checked attention source for this fixed DMS
workload, but not reordered or assumed to be a KVzap cold source. The fresh
control replay again observes 269 nonmonotonic layer/KV-head orders. It remains
functional/trace-derived software evidence, not capacity, traffic, timing,
hardware, quality, architecture, or RTL evidence.

### Cross-frontend evidence archive and next plan

The present stopping point is recorded by
`analysis/cross_frontend_residency_evidence_archive_20260915.md`; it preserves
Route-A persistent-packed KVzap as the primary architecture path, treats Llama
as two-anchor KVzap portability evidence, SnapKV as one-shot packed-residency
evidence, and DMS as dynamic-resident boundary evidence. It deliberately does
not claim observed SnapKV decode behavior or a universal DMS position field.

The planned C0--C5 Commonality Study is
`analysis/cross_frontend_commonality_study_plan.md`. It first derives a
provenance-bound semantic descriptor and realization extensions, then tests
candidate source traversal/optional composition without forcing any frontend
into hot/pending/packed cold lifecycle. It neither selects hardware resources
nor authorizes architecture specification or RTL.

### C0 implementation — cross-frontend evidence index

C0 is implemented by `tools/archive_cross_frontend_c0_evidence_index.py`. It
is a new-output, no-model gate that hash-binds only the archive-named completed
Qwen A4.2.14, Qwen/Llama M6, SnapKV P2, and DMS M4 JSON artifacts. It verifies
schemas/statuses, archive-recorded SHA-256 values, and semantic-boundary
guards. SnapKV's unobserved generated-token/decode state must remain explicit
unavailable/null; DMS's native active-resident/no-replacement state remains
literal. C0 opens no raw trace/tensor payload and is not a descriptor,
architecture, resource, hardware, or RTL result.

The accepted C0 report is
`analysis/experiments/cross_frontend_c0_evidence_index_01/cross_frontend_c0_evidence_index_report.json`,
SHA-256 `8a7636c2cce353ae1ba6099abb19861694d8789a6b23c8063825aeb88a750cc4`.
It verifies all four archive source bindings while loading no model or raw
payload. The next eligible step is C1 descriptor specification, not hardware
design.

### C1 implementation — typed semantic descriptor

`tools/build_cross_frontend_c1_semantic_descriptor.py` is the next no-model
Commonality Study gate. It verifies that all four JSON inputs still match the
C0-bound SHA-256/schema/status records and, by default, their literal paths,
then writes a new
`cross-frontend-c1-semantic-descriptor-1.0` availability matrix. The v1 core
is limited to model topology, identity, epoch, decision, visibility, position
provenance, traversal order, and attention binding at `(model, layer, kv_head,
epoch)` grain. Every value is explicitly `observed`, `derived`, `modeled`,
`unknown`, or `not_applicable`; unavailable values require reasons.

This gate deliberately leaves KVzap hot/pending/packed lifecycle, SnapKV
one-shot state, and DMS dynamic slots as realization extensions. It preserves
SnapKV generated decode as unknown, and separately records DMS arrival serial,
unknown literal original position, and required native traversal order. C1 is
not a common hardware interface, resource contract, architecture decision, or
RTL gate; it only prepares provenance-preserving C2 adapters.

For a remote replica, an explicit hash-preserving relocation is allowed only
into a fresh staging location whose manifest bytes exactly match the C0
SHA-256; the output retains both the C0-bound origin and staging path. It is
not permission to overwrite or merge a divergent same-name experiment artifact.

The accepted local output is
`analysis/experiments/cross_frontend_c1_semantic_descriptor_01/cross_frontend_c1_semantic_descriptor_report.json`
(SHA-256 `7b37e8f0945018f6b387085ea129f10758962dd987b4d8437cb243c7a45677a7`).
It revalidated every C0-bound input and typed all eight core semantic fields
for each frontend class without loading a model or selecting an interface,
resource parameter, architecture, or RTL target.

The matching remote `zsy` replica is stored at
`analysis/experiments/cross_frontend_c1_semantic_descriptor_remote_replica_01/cross_frontend_c1_semantic_descriptor_report.json`
with SHA-256 `58a1dda80511f4f580853b0aaa32c8aa82b77133db472b315ad2adb5f839f1d0`.
It used a fresh staging directory containing byte-identical C0-bound manifests
because the existing remote same-name Qwen A4.2.14 artifact had a divergent
hash; it did not modify that artifact and remains a provenance replica only.

### C2 implementation — realization-specific projections

`tools/build_cross_frontend_c2_realization_adapters.py` consumes the accepted
C1 descriptor and its hash-bound four source manifests. It emits one semantic
projection for KVzap persistent-packed, SnapKV one-shot packed, and official
DMS dynamic-resident-slot realization. The gate requires all eight core fields
to retain their C1 status and evidence pointer; an unavailable field must stay
null with a reason. Thus it explicitly rejects fabricated SnapKV decode data,
and DMS arrival serial remains distinct from unknown literal position.

The accepted C2 report is
`analysis/experiments/cross_frontend_c2_realization_adapters_01/cross_frontend_c2_realization_adapters_report.json`
(SHA-256 `7e14af14250b0143b37a9462bea152ce67b44cd9d227e37ae88e31ea24f43acb`).
It keeps separate KVzap model anchors and realization extensions; it establishes
no shared cache/hardware interface, resource/performance conclusion,
architecture decision, parameter, or RTL readiness. C3 may now compare the
three projections without inventing fields.

The matching remote `zsy_1` replica is
`analysis/experiments/cross_frontend_c2_realization_adapters_remote_replica_01/cross_frontend_c2_realization_adapters_report.json`
(SHA-256 `3dd5e120438db7406f02482ba74b50afaf9c8048d5c43cc9228234919e70b568`).
It binds the accepted C1 remote replica and byte-identical staged manifests;
it is a cross-host provenance reproduction, not new model or hardware evidence.

### C3 implementation — commonality classification

`tools/analyze_cross_frontend_c3_commonality.py` consumes the completed C2
report and produces a hash-bound per-field status matrix together with explicit
invariant-candidate, frontend-specific, and unresolved lists. It accepts a
candidate only when every prerequisite field is observed for all three
frontends. Therefore it can state the need to preserve each frontend's required
traversal order, but cannot turn that into one shared order or cache format.

The accepted C3 report is
`analysis/experiments/cross_frontend_c3_commonality_matrix_01/cross_frontend_c3_commonality_matrix_report.json`
(SHA-256 `6d9e16d618dc9d779db60d6a408b87c3257e3aa2e33394e4c4e425032607fea0`).
It identifies abstraction-level identity, epoch/decision scope, order
preservation, and comparator obligations; it retains SnapKV decode/lifecycle,
DMS literal position, physical/temporal resources, and universal source
composition as unresolved. It selects no interface, parameter, architecture,
or RTL target. C4 may now use each frontend's own accepted comparator.

The matching `zsy_1` remote replica is
`analysis/experiments/cross_frontend_c3_commonality_matrix_remote_replica_01/cross_frontend_c3_commonality_matrix_report.json`
(SHA-256 `74fc3eb42a3231904bc6762221c4ea41590c48813aa27b1267107560d8834a0f`).
It is cross-host provenance reproduction over the accepted C2 remote replica,
not additional model, resource, or hardware evidence.

### C4 implementation — comparator-bound traversal study

`tools/build_cross_frontend_c4_attention_primitive_study.py` binds accepted
C2/C3 reports and rechecks the literal comparator/traversal assertions in the
KVzap core, SnapKV P2/P3 summary, and DMS M4 manifest. It does not rerun model
attention. The three reports explicitly retain KVzap's optional one-to-three
source composition, SnapKV's single canonical terminal-prefill source, and
DMS's single native active-resident source in required native order.

The accepted C4 report is
`analysis/experiments/cross_frontend_c4_attention_primitive_study_01/cross_frontend_c4_attention_primitive_study_report.json`
(SHA-256 `558f5a9c9c4c09c6ad9d4f4d4a562182be8e2841b10362f7b4cce6e0a158c715`).
It supports only a frontend-bound ordered variable-length source traversal
abstraction under each accepted comparator; it establishes no common source
order/cache, scheduler/resource contract, hardware interface, architecture,
parameter, or RTL result.

The matching `zsy_1` remote replica is
`analysis/experiments/cross_frontend_c4_attention_primitive_study_remote_replica_01/cross_frontend_c4_attention_primitive_study_report.json`
(SHA-256 `6808293d0e49e34c84db9e59058407049ec788d4ac3289661204b381a6310087`).
It is cross-host provenance reproduction over the accepted remote C2/C3 chain,
not a new attention execution, resource, or hardware result.

### C5 implementation — evidence-bound direction decision

`tools/build_cross_frontend_c5_direction_decision.py` verifies the hash chain
from C0 through C4 and writes a direction-decision memo, not another hardware
study. It keeps Route-A persistent-packed primary only because C3/C4 retain
KVzap's distinct lifecycle while finding only a frontend-bound semantic
traversal abstraction; it rejects promoting that abstraction to a common cache
or hardware direction.

The accepted C5 report is
`analysis/experiments/cross_frontend_c5_hardware_direction_decision_01/cross_frontend_c5_hardware_direction_decision_report.json`
(SHA-256 `f7f3aec661602e5ec8febb7a43418c16cdf3dfc27e84a808a084b737d3c06fff`).
It makes Route-A persistent-packed the research/architecture primary path but
does not select FIFO/PTE/page/bank/burst/merge/PE/scheduler/controller settings,
freeze an architecture specification, or authorize RTL. Those require separate
resource-contract and workload-envelope/fallback evidence.

The matching remote `zsy_1` provenance replica is
`analysis/experiments/cross_frontend_c5_hardware_direction_decision_remote_replica_01/cross_frontend_c5_hardware_direction_decision_report.json`
(SHA-256 `1e45e60713ce6256df33c5efb06b5db93f1ecf6a630b9de7fb916b9d730868b3`).
It reproduces the complete remote C0--C4 hash-bound decision chain only; it
does not add a semantic execution, resource model, hardware measurement, or
RTL authorization claim.

The accepted output is
`analysis/experiments/snapkv_route_a_p3_semantic_qwen3_8b_01/`, manifest SHA-256
`56cd9ca61d303be0154ec12c2934ee4b71c08332d8dc8d32c5e09ca27c73ff37`. It
revalidated the completed P0 manifest/stream and P1 report hashes recorded
above. All 36 x 8 layer-head states consumed their 891 terminal P0 actions
exactly once (256,608 total) and agreed with P1 P=64: hot=64, packed=381,
pending=0, six pages consisting of five full pages and a 61-token tail. The
FP32 same-mask guard passed. Executed-dtype ULP recorded one 79-ULP
reduction-order diagnostic (layer 3, KV head 6, query head 26), with maximum
associated FP32 absolute difference `2.9802322387695312e-08`; it is not a
strict ULP pass or a merge-precision/hardware selection.

### A4.3.0 implementation — pre-spec resource, envelope, and fallback gate

`tools/build_kvzap_route_a43_resource_contract_envelope_gate.py` consumes only
completed C5, A4200/A4201/A4211/A4214, M6, and A317/A318 reports, writes a
fresh report, and runs no model. It retains the five unresolved resource fields
as candidate/model-only axes, keeps the six conditioned Qwen/Llama rows
separate, and requires Full-KV bypass to remain the explicit
zero-admission/zero-cold-ownership control. A318 is a modeled
contract-breach-risk boundary, not controller timing.
Its Qwen input guard also requires A4214 to bind the supplied A4211 hash and
to be one of M6's explicit reconciled A4214 raw serializations.

Passing A4.3.0 means only that its inputs form an auditable next-study ledger.
It does not select FIFO/PTE/page/bank/burst/merge/PE/scheduler/controller
parameters, establish an architecture specification, or authorize RTL.

### A4.3.1 implementation — bounded policy-on pending-state snapshots

`tools/analyze_kvzap_route_a431_policy_pending_staging_envelope.py` consumes
three fresh, accepted Qwen all-layer/all-KV-head paired-mask policy-on manifests
at the budget-one pending witness point. It records only the pending-token
state visible to Route-A attention comparisons, preserving retrieval,
summarization, and reasoning rows. It rejects a missing workload or any change
to the functional control. This is not a FIFO high-water mark at admission
arrival/completion and cannot select a finite FIFO depth or controller timing.

The underlying policy-on backend still rejects non-contiguous logical cache
positions. Its failure-only report is bounded to scalar sequence context; it
does not change Route-A semantics or count as a successful workload artifact.
Accepted source commands require exactly one visible CUDA device and record the
visibility environment. Multi-device `device_map=auto` is not an accepted
execution mode for this Python policy hook; this restriction does not select a
hardware architecture or imply a performance result.
The accepted source manifests use schema
`kvzap-route-a40-policy-on-qwen-gate-1.5` and the archived Qwen numerical
contract: ULP greater than 16 is bounded record-only context, while FP32
same-mask and the quantization-aware executed-dtype close envelope are hard
guards. Raising the ULP limit is not an accepted workaround, and these
diagnostics do not select merge precision or another hardware parameter.

### A4.3.2 implementation — policy-on lifecycle transitions

The optional `--record-lifecycle-transitions` mode creates an additional
trace-on Route-A replay after the normal trace-off replay. It must preserve the
Route-A answer and original-mask decisions exactly. Its gzip JSONL contains
only scalar state transitions per layer append: before maturity, after
maturity, and after the declared budget-one reference admission action. The
companion no-model A4.3.2 analyzer preserves all three workload rows and
hash-binds their transition artifacts. Neither artifact observes FIFO arrival
or completion, service time, overflow, or physical resource behavior.

### A4.3.3 implementation — conditional untimed staging recurrence

The A4.3.3 analyzer accepts only the three A4.3.2 sources, verifies their
budget-one aggregate pending recurrence, then sweeps declared post-append
service counts and aggregate pending thresholds. Its results are explicitly
conditional scalar comparisons: they do not model a per-head queue, page
sealing, arrival/completion timing, FIFO overflow, or a hardware controller.
They must not select Qwen-specific hardware parameters; a Llama-equivalent
envelope remains a required later gate.

### A4.3.4 implementation — prefill micro-event reference

`--prefill-maturity-chunk-tokens` is default zero and requires the trace-on
lifecycle replay. A positive value slices only a contiguous prefill append in
the Route-A reference state; it does not alter the predictor, mask, model
cache, or default pruning path. The micro-event trace is accepted only when it
matches batch Route-A answer and original-mask decisions under the existing
numerical and ownership guards. It is not a controller timing or physical page
experiment.

### A4.3.5 implementation — micro-event quantum comparison

The A4.3.5 analyzer accepts exactly three workloads at each of Q=1, 8, and 32
under the chunk-64 micro-event contract. It rejects answer divergence across
the quantum sweep and reports only hash-bound functional lifecycle state. It
selects no hardware service rate, FIFO depth, page/bank/burst behavior, or
Qwen-specific architecture parameter.

### A4.3.6 implementation — conditioned Llama micro-event comparison

The Llama follow-up is deliberately conditioned on M5.1's fixed eight-token,
non-EOS continuation rather than reusing Qwen's natural trajectory. Each of
the three Llama workloads is run at Q=1, 8, and 32 with chunk-64 trace-on
micro-events. The source requires the reviewed default-off Linear predictor
override; M0/M1/M5.1 hash binding; dense-only online mask decisions; exact
mask and fixed token-trajectory replay by both trace-off and trace-on Route-A;
all 32 layers and 8 KV heads; numerical-guard work; and timestamp-free,
layer-contiguous lifecycle records. The aggregate accepts only those nine
sources. It retains M5.1's record-only ULP context as non-strict evidence and
does not select cross-model or Llama-specific controller, FIFO, page, bank,
burst, merge, or architecture parameters.

### A4.3.7 implementation — non-pooled cross-anchor Q report

The A4.3.7 analyzer accepts only the completed A4.3.5 Qwen and A4.3.6 Llama
aggregate reports. It hash-binds both, rejects incomplete Q/chunk/workload
contracts, preserves the Llama fixed-continuation and record-only ULP context,
and emits six separate model/workload direction rows. Each row compares only
its own Q=1, 8, and 32 logical state summaries. The report deliberately has no
cross-model statistic, common range, or hardware selection; a sign difference
between later rows is dependence evidence rather than a reason to change any
accepted source.

### A4.4.0 implementation — deferred Full-KV-to-Route-A activation gate

`tools/run_kvzap_llama31_a440_deferred_activation_gate.py` introduces a
default-off policy backend for an explicit functional commit.  It does not
alter the normal KVzap pruning path.  The backend keeps native Full KV
authoritative while journaling online predictor decisions, has no Route-A
logical state before commit, then hydrates logical hot/pending/packed history
from that cache prefix and applies one existing reference admission action.
The paired `D=8` end-before-activation branch must remain pure Full KV, while
the `D=1` branch must commit exactly once and exercise post-commit same-mask
numerical guards under M5.1's existing fixed-continuation/record-only context.

The output serializes only scalar activation partition/page events and
timestamp-free post-commit lifecycle records.  It is functional and
trace-derived evidence, not measured or modeled hardware evidence: it neither
observes native allocator release nor reports physical capacity, transfers,
HBM traffic, bursts, FIFO occupancy/depth, timing, throughput, energy, area,
or any final resource/microarchitecture choice.  It is a conditioned Llama
anchor gate and deliberately cannot pool Qwen and Llama into one hardware
contract.  Capacity protection after Route-A activation remains a distinct
future contract.

### A4.4.1 implementation — Qwen deferred activation gate

`tools/run_kvzap_qwen_a441_deferred_activation_gate.py` applies the same
default-off backend transition to the Qwen3-8B Route-A anchor under its frozen
Gate-A model/predictor provenance and accepted quantization-aware numerical
guard.  It binds the completed A4.3.5 Qwen source only as prior workload
provenance, not as a replayed mask or numerical pool.  Each workload has a
native Full-KV reference, `D=8` pure-bypass branch, and `D=1` one-commit branch
with forced Full-KV token inputs after activation.  The gate requires a
single-visible-device execution environment because the Python hook is not an
accepted multi-device automatic-dispatch integration mode.

Its scalar commit/page and post-commit lifecycle outputs are functional and
trace-derived only.  They prove neither natural generation behavior nor native
cache reclamation, physical allocation/traffic/bursts, FIFO/service timing,
or any common Qwen/Llama resource contract.  A subsequent no-model report may
compare only per-anchor contract predicates; it must not pool activation
counts or select hardware parameters.

### A4.4.2 implementation — hash-bound cross-anchor contract closeout

`tools/analyze_kvzap_route_a442_cross_anchor_activation_contract.py` runs no
model.  It accepts only completed Qwen A4.4.1 and Llama A4.4.0 reports,
recomputes report and referenced post-commit trace hashes, parses the gzip
scalar traces, and rejects missing layer coverage, timestamps, non-decode
rows, or a broken bypass/activation/numerical-guard invariant.  Its output has
one preserved row for each anchor/workload and a boolean matrix for contract
parity.  It intentionally does not calculate a Qwen/Llama average, range,
common resource envelope, or microarchitectural parameter.

Consequently, its completion is a no-model archival semantic decision, not
measured or modeled hardware evidence.  Logical state totals remain inputs for
the later Capacity Protection Contract and resource models; they must not be
called physical memory, traffic, bursts, FIFO capacity, latency, throughput,
energy, area, or an architecture specification.

### A4.5.0 implementation — logical Capacity Protection Contract replay

`tools/analyze_kvzap_route_a450_capacity_protection_replay.py` is a no-model,
trace-derived boundary replay on the completed A4.4 Qwen/Llama sources. It
first invokes the A4.4.2 input validators, then scans declared logical pending
high-watermarks against the maximum selected-layer aggregate pending state at
activation and subsequent pre-append boundaries. A crossing enters a one-way
`protected_full_kv` state: native Full-KV is already retained, Route-A logical
admission/drop is counterfactually frozen, and no re-entry occurs in the
bounded trace. It retains every anchor/workload/high-watermark row separately.

This is deliberately not a FIFO occupancy, capacity, overflow, service-rate,
or controller-timing result. The replay cannot install a real native attention
switch or prove output preservation; a later model-on protection gate is
required. It contains no physical allocation/traffic/burst, HBM/DMA, latency,
throughput, energy, area, architecture-specification, or RTL claim.

### A4.5.1 implementation — model-on layer-local protection primitive

`CapacityProtectedDeferredActivationRouteAPolicyAttentionBackend` extends the
default-off deferred reference with a one-way local transition. At the
post-hydration pending boundary it records scalar state, freezes Route-A
`next_position`, clears the captured current mask, and delegates current/later
calls to retained native Full-KV attention. It rejects missing native fallback,
post-freeze state mutation, below-boundary transition, or re-entry. Default
KVzap pruning behavior remains unchanged.

`tools/run_kvzap_route_a451_capacity_protection_semantic_gate.py` binds each
anchor A4.4 report and its A4.5.0 `C=1024` witness before model load, then uses
the fixed continuation with forced Full-KV token inputs. It produces separate
Qwen/Llama reports and requires one visible CUDA device. This is a layer-local
primitive, not a request-global controller/look-ahead or within-append capacity
guarantee. `C=1024` is a logical probe, not FIFO capacity/service or a hardware
choice. Results remain functional only: no allocator/reclamation, physical
capacity, HBM/DMA traffic, burst, timing, latency, throughput, energy, area,
architecture specification, or RTL conclusion is authorized.
The runner establishes offline mode before importing the HF libraries. Thus a
missing cached model/predictor auxiliary file fails explicitly; it must not
cause an incidental metadata download or a substituted provenance path.

### A4.5.2 implementation — request-global controller reconciliation

`tools/analyze_kvzap_route_a452_global_protection_controller_reconciliation.py`
binds A4.4, A4.5.0, and A4.5.1 reports for both anchors. It verifies that each
actual A4.5.1 layer-local protected set exactly equals the corresponding A4.4
activation `pending >= C=1024` set, and that all retained local events use the
activation boundary with native fallback and frozen Route-A state. It then
records the first ordered layer observation at which a request-global latch can
be formed and declares all-layer action effective only in the next decode
epoch: lower layers already completed in the current epoch are not rewritten.

This is a no-model semantic reconciliation, not an implementation of a
request-global controller or a controller-delay measurement. It creates no
FIFO/service/page/bank/burst/merge/scheduler selection, physical capacity or
traffic result, timing/performance result, architecture specification, or RTL
authorization. Qwen and Llama rows remain separate.

### A4.5.3 implementation — model-on next-epoch request-global protection gate

`RouteAGlobalProtectionCoordinator` is request-scoped and accepts only ordered
post-hydration/pre-append activation observations. Its first `pending >= 1024`
observation latches global protection. It commits an effective position only
when every layer has completed that activation epoch, at one subsequent decode
position. `GlobalNextEpochCapacityProtectedRouteAPolicyAttentionBackend` keeps
the A4.5.1 local crossing behavior for the current epoch, then freezes and
delegates every layer to retained native Full-KV attention at the coordinator's
committed next epoch. The default pruning path is unchanged.

`tools/run_kvzap_route_a453_global_next_epoch_protection_gate.py` binds A4.5.2
and its A4.5.1 source reports, requires cached artifacts before Transformers/HF
initialization, and runs Qwen and Llama separately on one visible CUDA device.
It verifies the controller observation order/latch/boundary, all-layer
next-epoch native fallback, frozen logical state, lack of re-entry, and forced
Full-KV input preservation. This establishes functional control semantics, not
controller timing/broadcast behavior or a resource result. `C=1024` does not
select FIFO/service/page/bank/burst/merge/PE/scheduler or any architecture
parameter; no physical traffic, latency, throughput, energy, area,
architecture-specification, or RTL conclusion is authorized.

### A4.5.4 implementation — protected Route-A shadow-state disposition gate

`ReclaimingGlobalNextEpochCapacityProtectedRouteAPolicyAttentionBackend` is a
default-off A4.5.3 variant. At the already-authorized next-epoch global native
fallback, it snapshots scalar Route-A hot/pending/packed/page state and replaces
the live Route-A state with an access-failing tombstone. Its native fallback
path accepts only that tombstone; any later Route-A state access fails closed.
The tombstone is an ownership guard, not a Python allocator operation or a
claim that a physical page has been released. Retained native Full-KV remains
the sole authority; default pruning behavior is unchanged.

`tools/run_kvzap_route_a454_protected_shadow_state_reclamation_gate.py` binds
the A4.5.3 report plus its A4.5.2/A4.5.1 chain, validates the former controller
and local-trigger contracts, then runs each anchor separately on one visible
CUDA device. It requires all-layer next-epoch native fallback and tombstones,
head-total-conserving logical inventories, no shadow access/re-entry, preserved
forced Full-KV inputs, and retained native cache. Its inventory is functional
state only: it cannot measure allocation/free behavior, bytes, physical
capacity, HBM/DMA traffic, bursts, FIFO/service/overflow, timing, latency,
throughput, energy, area, architecture specification, or RTL.

### A4.6.0 implementation — Route-A-active long-horizon steady-state gate

`tools/run_kvzap_route_a460_steady_state_gate.py` binds A4.4.2 before model
load, then uses a fixed 64-token Full-KV reference only as token-input source.
After the `D=1` activation commit its Route-A branch remains active and rejects
fallback/protection. A lifecycle recorder exports all-layer/all-KV-head,
timestamp-free post-commit transitions; its final 32 decode append opportunities
are checked for a sustained non-decreasing pending-growth witness. This is the
normal persistent-packed path, not a permanent native Full-KV backing design.

The finite-horizon tail is functional logical state only. It is not a proof of
indefinite stability or an observed service timeline, FIFO capacity/occupancy,
overflow, physical allocation/traffic/burst, timing, latency, throughput,
energy, area, architecture specification, or RTL. Qwen and Llama outputs stay
separate and select no hardware parameter.

### A4.6.1 implementation — source-separated activation-burst logical envelope

`tools/analyze_kvzap_route_a461_activation_burst_envelope.py` is a no-model,
hash-bound closeout over A4.4.2 and completed Qwen/Llama A4.6.0 reports. It
does not rerun a model. For every anchor/workload it checks the A4.4.2 binding,
the lifecycle trace hash, layer/KV-head coverage, timestamp-free `q_len=1`
events, and the per-event pending/packed conservation equations. It then
retains—without cross-anchor pooling—the activation-commit logical inventory
separately from subsequent logical append opportunities.

The resulting integer distributions are source-separated workload inputs for a
later explicitly assumed resource model. They do not observe physical
activation bursts, FIFO occupancy/capacity, service rate, overflow, allocation,
bytes, HBM/DMA traffic, page/bank/PTE requirements, timing, latency,
throughput, energy, area, architecture specification, or RTL. A4.6.1 selects
no hardware parameter and does not revive Full-KV backing as the normal path.

### A4.6.2 implementation — multi-horizon logical admission-service envelope

`tools/analyze_kvzap_route_a462_activation_service_envelope.py` hash-binds the
complete A4.4.2/A4.6.0/A4.6.1 source chain and runs no model. It initializes
per-head backlog from A4.6.1 activation pending inventory, replays only mature
kept append arrivals, and searches the minimum logical service quantum that
drains every head by each of the `1,2,4,8,16,32,62` logical append-opportunity
horizons. It records per-head backlog/drain/reaccumulation/service state and
per-layer fairness spread under two explicit models: independent per-stream
optimistic service and shared per-layer unit-token round-robin service.

The quantum is a model-only tokens-per-append-opportunity variable. It is not a
cycle, service rate, FIFO depth/capacity, bandwidth, HBM/DMA traffic, physical
burst, or a hardware scheduler/resource choice. The A4.6.2 model is bounded by
the trace prefix and serves only as input to later physicalization-cost and
attention/admission-contention DSE; it selects no hardware parameter, does not
establish net benefit, and does not reintroduce Full-KV backing on the normal
Route-A path.

### A4.6.3.0 implementation — physicalization mapping contract

`tools/analyze_kvzap_route_a4630_physicalization_mapping.py` is the first,
no-model substep of A4.6.3. It hash-binds A4.4.2 through A4.6.2, replays each
modeled per-head candidate, and validates its granted/final-pending state. It
then emits separate eager-copy and sealed-page-copy-with-tail-reference
inventories over `P={16,64,128}`: payload token units, page allocation/seal/tail,
PTE/position metadata records, and post-service dual-source merge-state records.

This is an explicit mapping sensitivity, not evidence that a lifecycle event
caused a real transfer. Its units are not measured KV reads/writes, bytes,
HBM/DMA traffic, transactions, bandwidth, timing, or hardware resources, and it
selects neither mapping nor page/PTE metadata format. A4.6.3.1 remains separate:
only it may combine these named inventories with continuous attention in an
abstract contention model.

### A4.6.3.1 implementation — aggregate attention/admission contention envelope

`tools/analyze_kvzap_route_a4631_attention_admission_contention.py` consumes
the complete A4.6.3.0 mapping sensitivity and its A4.6.1 source traversal
inventory. It compares isolated, attention-first, and reserved-share abstract
work requirements under named cost profiles, without selecting a mapping/page
or interpreting units as physical traffic, cycles, bandwidth, FIFO, or hardware
resources. It is aggregate and bounded-horizon only; A4.6.2 deadline/fairness
is inherited, not temporally re-simulated under shared arbitration.

### A4.6.3.2 implementation — temporal abstract contention replay

`tools/analyze_kvzap_route_a4632_temporal_contention_replay.py` is the separate
no-model temporal follow-up. It selects only the A4.6.2 layer-shared candidates
as a shared-fabric sensitivity; the independent per-head envelope remains an
earlier optimistic bound. At every recorded append opportunity it emits
retained-source `A_t^attn`, mature-kept `A_t^new`, pre/post-arrival logical
backlog, grant `G_t`, and post-grant backlog, with per-head drain/fairness state.
Each realised grant is passed through the named A4.6.3.0 eager or sealed-page
mapping, including page/PTE/position/merge records and endpoint tail references.
In particular, merge is a single post-service head/opportunity record, never a
per-token-grant record, and it remains separate attention-side work when an
opportunity has no admission grant.

It compares strict attention-first, hard non-borrowing reservation,
work-conserving reserved minimum, and a deliberately offline
backlog/deadline-aware sensitivity. Its named composite-work profiles and
attention-borrow accounting are not a real shared fabric, measured traffic,
cycles, service rate, FIFO, latency, or scheduler selection. Thus it can only
bound the question of fixed background service versus buffering plus elastic
arbitration; it does not select an implementation or establish net benefit.

### A4.6.4 implementation — causal elastic-admission contract

`tools/analyze_kvzap_route_a464_causal_elastic_contract.py` hash-binds the
A4.6.1 source, A4.6.3.0 mapping, and valid A4.6.3.2 report, but deliberately
does not pass the A4.6.2 quantum or evaluation horizon to its causal controller.
One global configuration supplies logical levels `{16,64,256}` and uses only
layer/head backlog, pending-cohort age, previous level, and hysteresis state.
It is identical across all anchor/workload rows and has a prefix-causality test.

The same-level offline oracle may see future arrivals solely as a clairvoyant
reference.  All actual grants retain named A4.6.3.0 mapping and separate
post-service dual-source merge accounting.  Logical level occupancy,
transitions, backlog, age, deadline, fairness, and borrow summaries remain
timestamp-free modeled quantities, not cycles, FIFO/bandwidth requirements,
traffic, timing, a selected scheduler, or hardware specification.
Its unit-token round-robin allocator bounds each head's grant by its current
pending cohort before updating any mapping inventory.

### A4.6.5 implementation — observer-only causal capacity envelope

`tools/analyze_kvzap_route_a465_causal_capacity_envelope.py` hash-binds the
A4.6.1 source, A4.6.3.0 mapping, and completed A4.6.4 report.  It replays the
same causal controller only to validate identical logical outcomes, then places
head-local and layer-shared caps as passive observers after arrival and before
grant.  No cap is passed to the controller or can change a grant, lifecycle
state, DROP decision, fallback, backing, or protection mode.

It records breach/excess/duration tails and service-shortage pressure, with
reasoning rows retaining high-level saturation and `Age_max` explicitly.  The
cap grids are global logical sensitivities, not FIFO depth, buffer organization,
physical capacity, traffic, timing, or hardware parameters.

### A4.6.6 implementation — equal-budget pending-organization contract

`tools/analyze_kvzap_route_a466_pending_organization_contract.py` extends the
capacity study without turning storage organization into a scheduler.  It
hash-binds the A4.6.1/A4.6.3.0/A4.6.4/A4.6.5 chain, independently replays the
fixed causal policy, and rejects a run unless its aggregate and per-head result
matches both A4.6.4 and A4.6.5.  Organization observers then receive the same
post-arrival/pre-grant vectors; they cannot modify arrivals, grants, controller
state, per-head FIFO order, admission, lifecycle state, DROP, fallback, or
backing.

Each comparison gives head-local, layer-shared, and hierarchical private-plus-
overflow ownership exactly the same per-layer logical capacity budget `C`.
Hierarchical points satisfy `N_head*q+C_overflow=C`; its quota fractions and
the common integral `C` grid are globally declared across anchor head counts.
The report provides equal-budget breach/excess/duration/stranding
summaries and `Cmin` zero-breach or named bounded-breach frontiers.  They remain
observer-only logical sensitivities, not an allocator or physical implementation
claim: no FIFO, descriptor, PTE, port, bank, byte, HBM/DMA, cycle, timing,
throughput, energy, area, protection, hardware parameter, architecture spec, or
RTL conclusion is allowed.

### A4.6.7.0 implementation — immutable pending-ownership semantic reference

`tools/analyze_kvzap_route_a4670_pending_ownership_reference.py` is the
functional prerequisite to organization-cost modeling.  It hash-binds A4.6.1
through A4.6.6, derives rather than re-schedules the fixed causal per-head
grants, and independently rechecks the A4.6.4/A4.6.5/A4.6.6 pending trajectory.
Each logical entry carries immutable birth/order/source identity.  Private,
shared, and hierarchical source affiliation can never cause private/shared
migration, a grant change, or source-age inversion: cross-source dequeue must
select the oldest per-head entry, even when that entry is older shared overflow
and newer items are private.

The output inventories activation enqueue/residency separately from append
enqueue/dequeue/release operations, source spans, cross-source
selection/switches, and concurrency.  It has no
finite capacity or allocator and does not claim descriptor/PTE layout, physical
accesses, ports, banks, bytes, HBM/DMA traffic, cycles, timing, throughput,
energy, area, protection, hardware selection, architecture spec, or RTL.
