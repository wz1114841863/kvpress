# Route-A A4.1 measured software-system plan

## Status and scope

This plan starts only after the accepted A4.0 replayed-mask functional control:
`analysis/experiments/route_a40_policy_on_qwen_all_layers_replayed_mask_01/`.
That artifact proves a semantic pairing for the named Qwen3-8B retrieval
request; it does not supply runtime, allocator, HBM, throughput, energy, or
hardware evidence.

The first A4.1 objective is a small, reproducible software measurement gate.
It must not change KVzap's threshold, 128-token hot-window rule, token
positions, or dense-source replay mask. It must not reuse elapsed time from
the A4.0 Python semantic runner.

## Compared paths

Every measured result must name exactly one of these paths:

1. **Full-KV bypass** — no Route-A state, admission, predictor mask, or replay.
2. **Same-mask dense KVzap replay** — a frozen mask-event stream feeds regular
   hot plus dense retained-cold K/V; it has no Route-A pending FIFO or pages.
3. **Same-mask Route-A replay** — the exact same frozen mask-event stream feeds
   hot, pending staging, and packed pages with online-softmax merge.
4. **Online controls** — online dense KVzap and online Route-A may be run only
   as separately labelled mask-stability controls. They are not a paired
   performance comparison because A4.0 observed 5 keep/drop flips in 268,992
   independent online decisions for the initial request.

The mask source must be collected once outside the timed repetitions, hashed,
and replayed exactly once per layer/head/position in paths 2 and 3. A4.1 must
report replay completeness and per-layer digest equality before interpreting a
paired result.

## Measurement stages

### A4.1.0 — harness and no-model guards

Before a model run, add unit tests for:

- CUDA synchronization and event timing wrappers that reject CPU-only timing;
- reset/peak-memory snapshot order and units;
- raw-repetition schema validation and percentile summaries;
- replay-source hash, exact-consumption, and new-directory-only output rules;
- component labels that prevent a dense-cold result being stored as Route-A.

The harness must expose `--help`, require an absent output directory, write a
manifest before/after status, and save raw per-repeat records rather than only
an average.

### A4.1.1 — one-layer/head component gate

Use the named retrieval request and a declared target layer/head. Run separate
component measurements for:

- predictor score/mask formation (reported separately, never hidden in an
  attention comparison);
- maturity/admission service, pending staging append, page append/seal, and
  page-table bookkeeping;
- same-mask dense-cold attention;
- Route-A hot, pending, packed partial attentions and online merge.

Run the semantic-coverage point (`admission_budget=1`) to demonstrate pending
work, then the model-derived candidate point (`admission_budget=512`) to
observe a less artificially backlogged state. These are distinct parameter
points and cannot be pooled.

Implementation is deliberately two-stage.  First,
`tools/collect_kvzap_route_a41_replay_source.py` runs one **untimed** online
dense-KVzap collection and writes a hashed, position-keyed replay NPZ for one
declared layer.  Then
`tools/run_kvzap_route_a41_component_gate.py` resets model/backend state for
each warm-up or reported run and measures only the replayed dense and Route-A
components.  Its Route-A callback names maturity-to-pending, admission/page
append/table, hot attention, pending attention, packed attention, and merge;
the dense callback names dense maturity/cold append and same-mask dense
attention.  The optional online dense predictor control has its own path and
cannot be pooled with the replayed pair.

Each callback synchronizes CUDA and resets PyTorch allocator peak state.
That makes the callback samples useful for component attribution, but invalid
as end-to-end decode timing; A4.1.2 must measure the whole decode region
without per-component synchronization.  A4.1.1 code and no-model unit tests
are available locally.  The first real-Qwen coverage-point artifact is
`route_a411_component_layer0_head0_budget1_02`; its results remain limited to
the named one-layer/head, backlogged replay configuration.

The backlogged coverage point must pass `--require-pending-nonempty`; this is
an explicit semantic-coverage guard, not a general A4.1.1 invariant.  The
candidate `admission_budget=512` point omits that flag because immediate
oldest-first service may validly leave no pending record at a decode query.

The first two accepted component artifacts are the `layer=0`, `KV-head=0`
backlogged point `route_a411_component_layer0_head0_budget1_03` and candidate
point `route_a411_component_layer0_head0_budget512_01`.  They share the exact
same replay NPZ and source answer digest.  The former observed at most 21
pending and 1 packed token; the latter observed 0 pending and 22 packed
tokens, as required by the two admission policies.  Both are valid component
coverage observations only.  Their current summary groups report callback
invocations (70 or 280), while the independent reset-run count is 10.  Preserve
the raw rows. Schema-1.1 now adds an explicit per-`execution_order` aggregate
distribution before using A4.1.1 results to compare variability between
configurations: time is summed and allocator peak is maximized within each
reset run, while callback-level groups remain separately reported.

The next layer-0 head-6 point reuses the validated source stream. Its source
coverage reaches 195 mature dense-cold tokens, so with 64-token pages the
`admission_budget=512` candidate run must pass the explicit multi-page guard:
at least two packed pages and one sealed full page must be observed in the
actual Route-A state. Record full-page count and tail occupancy; do not infer
page behavior from token count alone. Run the budget-one counterpart with the
pending guard first; it is pending coverage, not multi-page coverage.

The head-6 budget-one and budget-512 multi-page artifacts have now passed.
The candidate state reached four pages with three full pages; tail occupancy
was also observed. Because those coverage fields are maxima across decode
calls, they must not be combined into a reconstructed single-call state.
Together with the schema-1.1 reset-run reports, this closes A4.1.1 for the
named request/layer/head. A4.1.2 may now build its no-component-sync
whole-decode runner, but no A4.1.2 result exists until that runner separately
passes replay, timing, reset, and baseline gates.

The first A4.1.2 `{0,18,35}` artifact
`route_a412_whole_decode_layers_0_18_35_budget512_01` passes those protocol
gates: its three-layer source has 22,416 events, all three paths have ten
reported reset runs and identical 8-token answer/token-ID digests, and replay
is complete. Its measured decode-stage CUDA-event means are 290.50 ms
(Full-KV bypass), 1347.80 ms (same-mask dense replay), and 1608.48 ms
(same-mask Route-A replay), with Route-A 19.3% above dense replay on this
single configuration. These timings characterize the Python reference only.
Its native DynamicCache remains dense and Route-A owns an additional copied
state, so the equal dense/Route-A PyTorch allocator peaks cannot be used as a
physical-memory result. Do not broaden layers or workloads yet; first run a
separate profiler diagnostic to localize Python/list/stack/merge and cache
overheads, then design any true cache-storage substitution independently.

A4.1.2.1 implements that diagnostic in
`tools/run_kvzap_route_a412_profiler.py`. It uses the exact A4.1.2 replay
source and runs the three paired paths with a separate `torch.profiler` capture
after unprofiled fresh-cache warm-up(s). Its artifacts are a Chrome trace and
normalized top-operator table per path, plus replay/answer/token-ID guards and
PyTorch allocator snapshots. It is intentionally one diagnostic capture, not
a repetition benchmark: profiler output is excluded from all A4.1.2 timing
summaries and can only identify reference overhead to guide a later,
independent cache-ownership/substitution design.

The first remote 1.0 diagnostic also established that Chrome traces can be
large because every small Python-reference operation emits CPU, CUDA-runtime,
kernel, correlation, and memory/shape events. Its raw traces remain valid for
inspection, but PyTorch 2.10 leaves the legacy `cuda_time_*` aggregate fields
empty. The 1.1 runner reports generic `device_time_*` fields instead and must
be rerun in a new directory before ranking GPU-attributed operators. Trace
transfer may use lossless gzip compression; retain the original trace or a
documented decompression path, and never pool profiler values into timing
distributions.

### A4.1.2.2 — selected-head native-cold ownership gate

Before replacing cache allocation, establish that selected mature cold K/V is
not silently supplied by native dense cache during Route-A attention. The
minimal gate targets one layer and one KV head. It appends original K/V to the
same replayed-mask Route-A hot/pending/packed state, then NaN-poisons that
selected head's mature native-cache K/V cells. On every later attention call,
it verifies the old mature range is still poisoned; selected query heads use
Route-A attention, while all unselected heads/layers remain native. The same-
mask dense control and owned-cold Route-A generated-output relation is
recorded, rather than required to match: the existing per-head FP32 numerical
guard is the semantic criterion, and legal reduction-order differences can
alter later greedy tokens. Run budget one with pending required and budget 512/head 6 with
multi-page required. This is untimed and explicitly retains native tensor
allocation, so it is a semantic ownership guard—not cache compaction, allocator
measurement, physical-memory result, or performance result.

### A4.1.2.3 — first-generation-logit prefix diagnostic

The first ownership runs showed a token-0 drift. Before attributing it to
legal online-softmax reduction order, run one untimed context-prefill plus
question-forward diagnostic. It records finite status, NaN/Inf count, argmax,
top-k/margin, and dense/Route-A logit relation, as well as question query
length and q_len=1 policy call count. It intentionally consumes only a replay
prefix. This distinguishes a finite close-logit/top-1 flip from the more basic
failure mode in which a multi-token question forward falls back to native dense
attention after ownership poisoning. Do not broaden ownership coverage or take
timing measurements until this diagnostic is reviewed.

### A4.1.2.4 — causal multi-token bridge gate

Repair the discovered q_len>1 fallback before further ownership work. The
bridge appends question K/V one token at a time and replaces each selected-head
output from its causal Route-A prefix. Native attention receives zero selected-
head placeholders and supplies only unselected outputs. Require finite logits,
equal dense/Route-A first argmax, complete bridge token coverage, and poison
prior-read coverage. This is still a semantic prefix gate, not measurement.

Schema 1.1 corrects the paired baseline: the dense control must itself replace
selected q_len>1 outputs with a causal same-mask dense bridge. The 1.0 dense
control delegated that case to native Full-KV attention, so its Route-A logit
delta mixed intended pruning behavior with numeric error. Report the bounded
per-token selected-head attention summaries before interpreting final-logit
deltas. Do not require bitwise-equal logits: the declared equivalence contract
is the per-head FP32 `rtol`/`atol` guard plus the recorded execution-dtype ULP
limit; any downstream logit effect is diagnostic until characterized.

**Observed schema-1.1 narrow result (2026-09-04):**
`route_a4124_multitoken_bridge_layer0_head6_budget1_densebridge_01` consumed
the matching replay prefix for layer 0/head 6 and bridged all 22 question
tokens in both controls. Route-A's largest selected-head discrepancy was
`5.21540641784668e-08` in FP32 and `9.5367431640625e-07` after cast (one ULP,
below the configured 16-ULP limit); the resulting same-mask dense versus
Route-A final logits were bitwise equal in this run. The earlier `0.55078125`
delta is instead exactly the Full-KV versus valid same-mask-dense delta. This
localizes that value to intended mask semantics for this selected layer/head,
not packed online-softmax numerical error. It is one prefix diagnostic only,
not an accuracy, full-decode, timing, memory, or hardware conclusion.

### A4.1.2.5 — valid same-mask bridge under full-page/tail/multi-page coverage

Reuse the identical replay source, layer, head, model, and request from the
schema-1.1 budget-one gate, but set the Route-A admission budget to 512 and
require observed multi-page, sealed-page, and nonempty-tail coverage. Pending
staging need not be nonempty at this budget; it was separately covered at
budget one. The dense control remains the causal same-mask multi-token bridge.
Require finite paired logits, equal first argmax, per-token bridge coverage,
ownership poisoning, and all three observed page guards. This tests packed
page-boundary semantics, not timing, allocation, HBM, or throughput.

**Observed A4.1.2.5 result (2026-09-04):**
`route_a4125_multitoken_bridge_layer0_head6_budget512_multipage_01` completed
against the same immutable replay NPZ hash. It observed 191 packed retained
tokens for head 6: three pages total, two sealed full pages, and a 63-token
tail; pending was zero as expected at this high admission budget. All requested
page guards, both 22-token bridges, cold-ownership guards, finite-logit guard,
and paired first-argmax guard passed. Same-mask dense and Route-A final logits
were equal; Route-A's maximum selected attention difference was
`3.818422555923462e-08` FP32 and one execution-dtype ULP. This is one
layer/head prefix semantic result, not a physical-page allocation, performance,
or quality result.

### Next semantic objective — simultaneous all-KV-head ownership in layer 0

Schema 1.3 implements this objective: the ownership backend now replaces and
poisons every selected GQA group simultaneously when `target_kv_head=all`.
It preserves per-head diagnostics, while requiring every selected head to have
one bridge comparison per question token. Heads with no retained mature cold
state, short packed tails, pending staging, and head 6's multi-page state are
all valid cases. Run a budget-one gate with aggregate pending coverage, then a
budget-512 gate with aggregate multi-page/full-page/tail coverage; do not
require every head to have every page state. This closes the same-layer
cross-head interaction gap before expanding ownership semantics to multiple
layers. Both runs remain untimed prefix diagnostics.

**Observed A4.1.2.6 result (2026-09-04):** both
`route_a4126_allheads_layer0_budget1_pending_01` and
`route_a4126_allheads_layer0_budget512_multipage_01` completed with all eight
heads and 22 bridge comparisons per head (176 per bridge). Budget one observed
pending on heads 0, 1, 3, 5, and 6; budget 512 drained pending and observed
head 6 with three packed pages, two full pages, and a 63-token tail. Native
cold ownership and per-head numerical guards passed in both cases (maximum one
execution-dtype ULP). However, valid same-mask dense versus Route-A final
logits differed by `0.44921875` while retaining the first argmax. Do not expand
ownership to multiple layers yet: this requires a downstream all-head
accumulation diagnostic first. Also, schema 1.3's non-requested guard booleans
are vacuously true (`not requested or satisfied`); use the config flags and
coverage rows to interpret these two artifacts, and revise future schema output
to record requested and satisfied separately without editing them.

### Next semantic objective — all-head downstream-logit accumulation diagnostic

With the same request, replay source, layer-0 all-head selection, and both
admission budgets, capture bounded per-layer/per-question-token activation
relations for the paired dense and Route-A forwards. Store scalar summaries
only (shape, finite state, max/mean absolute difference, relative L2, and a
bounded maximum-location descriptor); never serialize hidden-state tensors.
The purpose is to determine whether the 0.449 final-logit delta originates at
the layer-0 post-attention output and predictably propagates through later
unchanged layers, or indicates an unintended cross-head/state mismatch. First
repair the guard-request metadata in the new diagnostic schema. This remains
untimed and is not a quality or performance experiment.

**A4.1.2.7 implementation:**
`tools/run_kvzap_route_a4127_allhead_activation_diagnostic.py` captures the
36 decoder-layer outputs only for each paired question forward and writes no
activation tensor. The result must first be run at budget one with aggregate
pending coverage, then at budget 512 with aggregate multi-page/full-page/tail
coverage. Review whether the first nonzero activation relation is layer 0 and
whether later-layer growth is a continuous downstream propagation. An earlier
layer difference, a nonfinite relation, missing layer capture, or missing
requested state is a semantic failure requiring diagnosis before multi-layer
ownership. First-argmax equality is recorded, not made a precondition, so a
finite drift remains inspectable.

**Observed A4.1.2.7 budget-one result (2026-09-04):**
`route_a4127_allheads_layer0_budget1_pending_activation_01` completed with all
36 layer summaries, every requested all-head bridge guard, and explicit
`any_pending: {requested: true, satisfied: true}` metadata. The first nonzero
paired activation relation is layer 0 (maximum `0.001953125`, relative L2
`0.0002011`), not a preceding layer. Differences then grow through unchanged
layers, reaching layer-35 maximum `16.0` and relative L2 `0.01665`, while all
activations remain finite and the paired final-logit maximum is `0.44921875`
with equal first argmax. This localizes the drift to post-replacement layer-0
activation propagation, consistent with accumulation of the per-head one-ULP
differences; it does not by itself prove page-layout independence. Run the
budget-512 page-state counterpart before deciding whether multi-layer ownership
is safe to pursue.

**Observed A4.1.2.7 budget-512 result (2026-09-04):**
the synchronized multipage artifact (directory suffix `_0`) completed with
explicit requested/satisfied multi-page, full-page, and tail-page guards. Its
activation relation is identical to the budget-one table at every reported
layer: first difference layer 0, layer-0 maximum `0.001953125` and relative L2
`0.0002011`, layer-35 maximum `16.0` and relative L2 `0.01665`, and paired
final-logit maximum `0.44921875` with equal first argmax. It simultaneously
observed head 6 with three packed pages, two full pages, and a 63-token tail.
This controls the pending-versus-packed page-state variable for this request:
the drift is attributable to all-head numerical propagation, not the admission
layout. It remains one layer/request prefix result; an explicit numerical
acceptance policy is required before multi-layer ownership expansion.

### A4.1.2.8 — fixed-horizon all-head continuation output-impact diagnostic

The A4.1.2.7 `0.44921875` maximum final-logit difference is a raw logit-space
maximum, not an answer-error rate. The observed first argmax is unchanged, but
any later greedy choice could in principle change if its decision margin is
smaller than the local paired-logit perturbation. Conversely, unchanged argmax
at one prefix does not prove the whole trajectory is unchanged. Before any
multi-layer expansion, run an untimed fixed-horizon diagnostic that separates
these cases.

`tools/run_kvzap_route_a4128_allhead_continuation_diagnostic.py` first makes a
same-mask dense 8-token greedy reference. It then runs Route-A twice: a
**forced** route using those dense token IDs, which retains an identical input
history and reports paired logit/argmax relations at every token offset; and
an **independent** Route-A greedy route, which reports the first generated
token mismatch and the token-ID digest. After an independent mismatch, later
rows are not paired numerical evidence because the model inputs differ. The
gate is fixed-length deliberately so all replay decisions are consumed and
checked. It stores only scalar/top-k metadata and token IDs, and includes no
timing region or profiler collection.

Run budget one with pending coverage first, then budget 512 with aggregate
multi-page/full-page/tail coverage. If all forced argmax values and all
independent IDs match over the declared horizon, the current one-layer/all-head
drift has no observed greedy-token consequence over that bounded replayed
continuation. A forced argmax change identifies a direct same-input decision
effect; an independent first mismatch identifies the earliest observed
trajectory difference. Neither outcome measures task quality or validates
multi-layer ownership, and neither is a performance result.

**Observed A4.1.2.8 budget-one result (2026-09-04):**
`route_a4128_allheads_layer0_budget1_pending_continuation_02` completed with
the explicit pending guard, all eight selected heads, native-cold ownership,
and complete consumption of the shared 7,472-event replay source in dense,
forced Route-A, and independent Route-A paths. Dense token IDs and independent
Route-A token IDs were identical for all eight generated offsets; forced Route-A
also retained equal paired argmax at every offset. The largest paired-logit
maximum was `0.640625`; the smallest dense top-1/top-2 margin was `21.5`.
Thus no greedy-token consequence of the layer-0 all-head drift was observed in
this fixed pending-state horizon. Run the budget-512 page-state companion next;
this remains neither a quality nor a performance conclusion.

**Observed A4.1.2.8 budget-512 result (2026-09-04):**
`route_a4128_allheads_layer0_budget512_multipage_continuation_01` passed its
explicit multi-page/full-page/tail-page guards. Head 6 reached four packed
pages, three full pages, and a 63-token tail with no pending state. All paths
again consumed the same 7,472 replay events; forced Route-A argmax and
independent Route-A token IDs matched dense for all eight offsets. The forced
and independent per-step paired-logit relation tables are exactly identical to
the budget-one artifact. The only recorded numerical change is the bounded
per-attention FP32 maximum (`5.2154e-08` versus `4.4703e-08`), with both
remaining one executed-dtype ULP. This controls pending versus packed page
layout for this one-layer horizon. The next semantic expansion is not all 36
layers: create a new immutable replay source for layers `{0,18,35}` and run the
same all-head forced/independent continuation diagnostic for that layer set,
pending before page-state coverage.

### A4.1.2.9 — `{0,18,35}` simultaneous all-head continuation diagnostic

`tools/collect_kvzap_route_a41_replay_source.py` already supports a layer set;
collect a fresh immutable online dense-KVzap source for exactly `{0,18,35}`
before installing the new gate. `tools/run_kvzap_route_a4129_multilayer_continuation_diagnostic.py`
then consumes that source in three untimed paths: all-layer same-mask dense
greedy, all-layer ownership Route-A forced with dense IDs, and all-layer
ownership Route-A independent greedy. The new
`RouteAColdOwnershipAttentionBackendSet` creates independent hot/pending/page
state and poison/read audits for every selected layer; it does not free native
cache allocation.

Run budget one with aggregate pending coverage first, then a separately sourced
or identically compatible budget-512 run with aggregate multi-page/full-page/
tail coverage. Require all three layers' replay consumption, every selected
layer/head causal bridge, finite outputs, and per-layer ownership guards. A
forced argmax change or independent first mismatch is an output-impact finding
that must be localized before all-36 expansion. Even a clean result remains a
single request/fixed-horizon semantic diagnostic, not timing, quality, memory,
HBM, or hardware evidence.

**Observed A4.1.2.9 budget-512 result (2026-09-04):**
`route_a4129_layers_0_18_35_budget512_multipage_continuation_01` passed all
three requested page-state guards with the identical three-layer source. It
observed no pending state, as expected, but observed layer-0 head 6 with four
pages/three full pages/63-tail and layer-18 head 3 with seven pages/six full
pages/62-tail. Every layer again completed replay, bridge, finite, and
ownership checks. Forced argmax and independent eight-token greedy IDs matched
dense throughout. The budget-512 per-step logit-difference table is not
bitwise identical to budget one (maximum `0.75` versus `0.5`), but its minimum
dense top-1/top-2 margin remains `20.0` and no decision changed. This controls
the two admission layouts for the three-layer scope. Next, collect an immutable
all-36-layer source and repeat the same fixed-horizon gate at budget one before
its budget-512 page-state counterpart; do not move to timing yet.

### A4.1.2.10 — all-36-layer simultaneous ownership continuation diagnostic

`tools/run_kvzap_route_a4130_alllayer_continuation_diagnostic.py` is now the
strict all-layer entrypoint. It shares the tested A4129 implementation but
accepts only the full decoder layer set, writes schema
`kvzap-route-a4130-alllayer-continuation-diagnostic-1.0`, and uses a separate
manifest name. First collect a new all-layer source with
`tools/collect_kvzap_route_a41_replay_source.py --target-layers all`; do not
reuse a `{0,18,35}` source. Then run budget one with aggregate pending coverage
and review all 36 layer/head bridge, replay, ownership, forced, and independent
relations before the budget-512 page-state counterpart. This remains untimed;
its only purpose is to close the all-layer semantic gap before a true storage-
substitution measurement implementation.

An all-layer execution-dtype ULP breach must not be handled by increasing the
limit blindly. The runner persists a scalar-only failure diagnostic naming the
layer, KV/query head, cache position, dtype, maximum-ULP component, its local
ULP spacing, and the paired FP32 difference. First determine whether the breach
is a near-zero ULP amplification with a small FP32 difference or a material
same-mask numerical error; then choose an explicit tolerance policy or fix the
reference reduction. The failed output directory remains immutable; rerun only
into a fresh directory after the diagnostic code is synchronized.

**Observed A4.1.2.10 numerical hold (2026-09-04):** the first all-36
budget-one forced continuation stopped at layer 8/head 3/query head 15/position
916 with BF16 component 20 at 26 ULP over the 16-ULP limit. Its recorded cast
difference was only `3.0268e-09`, at values near `-1.5e-08`; local BF16 spacing
was `1.1642e-10`. The paired vector maximum FP32 difference was `1.7136e-07`,
well below the mandatory `atol=1e-5`. Therefore this is a near-zero ULP
amplification diagnosis, not evidence of mask drift, native-cold reread, or an
FP32 packed-attention semantic failure. It is nevertheless a hold: no all-36
continuation/token relation or budget-512 result exists. Next implement a
bounded record-only ULP distribution diagnostic that retains the hard FP32
guard, counts/samples all ULP breaches, and does not call them accepted.

### A4.1.2.11 — all-layer execution-dtype ULP distribution diagnostic

`tools/run_kvzap_route_a4131_alllayer_ulp_distribution_diagnostic.py` is a
strictly diagnostic continuation of the A4130 hold. It uses the all-layer
replayed masks and retains the FP32 same-mask, replay, bridge, and ownership
guards, but changes only the response to a post-cast ULP breach from abort to
bounded scalar recording. Per layer it reports breach count, maximum ULP,
maximum scalar FP32 and executed-dtype differences, and no more than the
declared sample limit. It is not a relaxed acceptance criterion: a passing
completion means only that the distribution was collected without an FP32 or
state-semantic violation. Do not start all-layer budget-512, timing, allocator,
or profiler experiments from this result until the distribution is reviewed and
an explicit numerical policy is recorded.

### A4.1.2.12 — all-layer hard scale-aware executed-dtype guard

`tools/run_kvzap_route_a4132_alllayer_scale_aware_continuation_gate.py` turns
the A4131 evidence into a strict, scale-aware policy: FP32 same-mask remains
hard; BF16/FP16 ULP counts remain bounded observations; and the cast vector
that is actually inserted into the model must independently pass
`torch.testing.assert_close` under the same declared `rtol`/`atol`. The
entrypoint fixes all layers, ULP `record_only`, and cast-close
`scale_aware_enforce`; users
cannot turn either selection into a partial/all-ULP-only gate through CLI
overrides. A cast-close failure writes scalar-only location, observed/allowed
difference, and tolerance-ratio context. Run budget one first. Only if it
completes with replay, bridge, ownership, pending, forced, and independent
guards may the separately scoped all-layer budget-512 page-state gate be
considered; it still does not authorize timing or profiler work by itself.

**Observed A4.1.2.12 hold (2026-09-04):** layer 1/head 7/query head 31/position
915 differed by exactly one BF16 ULP (`6.1035e-05`) near `0.0093`; FP32 maximum
was only `1.1176e-07`. The direct post-cast tolerance was `1.0908e-05`, so it
rejected an explainable adjacent-BF16 rounding result at ratio `5.59375`. This
invalidates the A4132 guard formulation, not Route-A state semantics.

### A4.1.2.13 — all-layer hard quantization-aware cast guard

`tools/run_kvzap_route_a4133_alllayer_quantization_aware_continuation_gate.py`
hard-enforces the FP32 allowance plus one local execution-dtype spacing from
each separately cast output. It accepts adjacent BF16 rounding only after the
hard FP32 same-mask check, and rejects any cast difference outside that explicit
envelope with scalar-only context. Run budget one first; completion is not a
budget-512, timing, allocator, quality, HBM, or hardware result.

**Observed A4.1.2.13 budget-one result (2026-09-04):** the complete all-36
budget-one gate passed with the immutable 268,992-event source. All 288
layer/head selections consumed replay and bridged the question forward; FP32
and quantization-aware cast guards, ownership, pending coverage, forced IDs,
and independent greedy IDs passed. The seven formerly failing >16-ULP events
remain recorded, not hidden. This authorizes the bounded multi-page state gate,
not timing or allocator work.

### A4.1.2.14 — all-layer budget-512 page-state gate

`tools/run_kvzap_route_a4134_alllayer_quantization_aware_page_state_gate.py`
is a separate schema/entrypoint that pins `admission_budget=512` and requires
aggregate multi-page, full sealed page, and tail-page coverage before it loads
the model. It retains all-layer replay/bridge/ownership, hard FP32 and
quantization-aware cast guards, forced common-token and independent greedy
relations, and bounded ULP recording. Pending is intentionally not required.
Completion remains functional evidence only.

### A4.1.3.0 — no-model true-storage ownership contract

`kvpress/route_a_storage_contract.py` and
`tools/run_kvzap_route_a4135_storage_contract_gate.py` establish the narrow
precondition for a later adapter without pretending to free memory. They prove
per selected head that logical cache length is preserved, native retention can
be limited to the hot interval, and mature positions are exactly partitioned
between Route-A pending/packed retained records and original-mask drops. The
local synthetic gate passed budget-one pending and budget-512
multi-page/full-page/tail cases. It records `physically_freed: false`; next is
an adapter design/gate, not allocator or decode timing.

### A4.1.3.1 — external selected-head storage adapter (no model)

`kvpress/route_a_external_cold_storage.py` and
`tools/run_kvzap_route_a4136_external_cold_storage_adapter_gate.py` implement
the narrow next step. Stock `DynamicCache` derives logical length from its
physical K/V tensor length, so slicing a mature prefix would break cache
positions and masks. The adapter instead keeps explicit logical-length
metadata, physically retains only selected-head hot K/V, and makes Route-A
pending/packed state the sole selected mature-retained store. Its no-model
gate requires pending budget-1 and full-page/tail/multi-page budget-512
coverage with same-mask packed-attention equality.

This is functional storage-semantics evidence only. It does not attach to
Qwen, free native-cache slots, or authorize allocator/timing/HBM claims.

### A4.1.3.2 — Qwen external-cold interface semantic gate

`RouteAQwenExternalColdStorageAttentionBackend` and
`tools/run_kvzap_route_a4137_qwen_external_cold_storage_gate.py` attach the
external adapter at one replayed Qwen layer/head. The hook accepts newly
created K/V at their Qwen logical cache positions, maintains bounded selected
native-hot adapter tensors, and replaces selected attention through Route-A
state. Existing NaN poisoning stays active solely to reject an accidental
native mature-cold read. The gate is paired against same-mask dense replay and
records, rather than requires, later greedy-token equality.

Ordinary Qwen prefill is passed to the adapter as a single Route-A append and
one global admission service. Only the causal multi-token bridge appends one
token at a time. Splitting prefill would over-drain pending staging and would
not constitute same-policy evidence.

This remains untimed and leaves native DynamicCache allocated. A passing result
is necessary before designing a real Qwen cache interface, but it is not a
physical storage or allocator result.

### A4.1.3.3 — Qwen single-layer native-storage replacement prototype

`kvpress/route_a_qwen_cache.py` implements the first actual Qwen `Cache`
interface prototype for layer zero and one selected KV head. Its persistent
target-layer state contains dense K/V only for unselected heads. Selected hot
K/V is owned by the Route-A external adapter, selected retained mature cold is
pending/packed there, and selected dropped mature positions are absent. A
transient dense-shaped Qwen attention input is constructed per update because
the current Qwen attention interface still requires all KV-head slots; it is
not stored in the cache. A4138 validates this representation together with
same-mask policy attention and native-cold no-fallback guards.

The prototype remains batch-one/layer-zero/single-head and untimed. Its
transient view means no allocator, HBM, runtime, or throughput conclusion may
be drawn; those require a later measured implementation without this view.

### A4.1.3.4 — budget-512 native-storage page-state gate

`tools/run_kvzap_route_a4139_qwen_native_storage_page_state_gate.py` pins the
A4138 cache interface to admission budget 512 and requires selected-head
multi-page, sealed-full-page, and tail-page coverage. Its replay source must
be newly collected with layer 0 and the same budget; replay provenance is not
interchangeable merely because dense mask decisions may coincide. Pending is
not required because this admission point may drain it. This remains untimed
functional storage/attention evidence only.

**Observed A4.1.2.9 budget-one result (2026-09-04):**
`route_a4129_layers_0_18_35_budget1_pending_continuation_01` passed every
three-layer replay, bridge, finite-output, and ownership guard using the new
22,416-event source. Each selected layer consumed 7,472 events; all 24
layer/head selections bridged the 22-token question forward. Pending staging
was observed, and each selected layer had 17 native-cold poison/read checks
with eight prior-cold-read checks. Per-layer FP32 selected-attention maxima
were `5.2154e-08`, `1.5199e-06`, and `5.7220e-06` for layers 0, 18, and 35,
respectively; each was one execution-dtype ULP. Forced argmax and independent
eight-token greedy IDs matched same-mask dense; the largest final-logit
maximum was `0.5` versus a minimum dense decision margin of `20.0`. Proceed to
the budget-512 multi-page/full-page/tail counterpart, retaining this exact
source and fixed horizon. Do not infer quality or performance.

### A4.1.2 — all-layer end-to-end decode gate

After component timing is internally consistent, measure all selected layers
for the three paired paths. Begin with `{0,18,35}`, then all 36 layers. Hold
the request, seed, decoding settings, page size, threshold, window, dtype,
model revision, predictor revision, device, and replay mask source fixed per
comparison. Record generated length and answer digest, but do not require
Full-KV answer equivalence.

`tools/run_kvzap_route_a412_whole_decode_gate.py` is the first implementation
of this gate. It creates a new `DynamicCache` and policy state per path/reset
run, constructs context state outside the timer, then measures one
question-forward plus greedy-decode region. It records Full-KV bypass,
replayed dense, and replayed Route-A in seeded shuffled order. It does not
install the A4.1.1 component recorder. The first source/runner pair must cover
layers `{0,18,35}` and all KV heads; no A4.1.2 real-Qwen result exists until
that new source and runner output pass review.

## Repetition and timing protocol

The initial gate uses 3 unreported warm-up repetitions and 10 reported
repetitions per path/configuration. Each reported repetition must reset model
and backend state, synchronize before and after its timed region, and record
wall-clock plus CUDA-event elapsed milliseconds when applicable. If either is
unavailable, mark that field unavailable rather than substituting a proxy.

Report raw repetitions and count, min, median, mean, standard deviation,
P90, P95, and max. Run path order in a recorded, seeded shuffled order within
each configuration; report the exact order. The profiler run is separate from
the timing repetitions because profiler instrumentation changes execution.

## Memory and profiler protocol

For every reported repetition capture CUDA allocator snapshots in bytes:

- allocated and reserved immediately before the timed region;
- peak allocated and peak reserved during it;
- allocated and reserved after cleanup/synchronization.

These are PyTorch allocator observations, not physical HBM traffic. A separate
documented `torch.profiler` run may record operator time and allocator memory
events. Hardware traffic counters are optional and may be reported only with
the profiler/counter tool, version, command, scope, and counter definitions;
absence must be reported as unavailable.

## Required artifacts and gates

Each new `analysis/experiments/<new_id>/` directory must include:

- manifest: source hashes, git commit, versions, GPU/device, configuration,
  replay pairing mode, exact-consumption result, and measurement boundaries;
- raw JSONL/CSV repetitions with no overwritten run id;
- summary JSON/CSV with distribution statistics and unavailable fields explicit;
- separate profiler metadata/output references, if profiling was enabled.

Stop before broadening workload, length, or model coverage if a semantic guard,
replay digest, reset invariant, or timing/memory schema check fails. A4.1 may
produce measured software observations only. It does not validate modeled A3
cycle/byte claims, physical HBM traffic, hardware acceleration, energy, area,
frequency, or RTL readiness.
