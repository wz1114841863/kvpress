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
mask dense control and owned-cold Route-A path must generate identical answer
and token IDs. Run budget one with pending required and budget 512/head 6 with
multi-page required. This is untimed and explicitly retains native tensor
allocation, so it is a semantic ownership guard—not cache compaction, allocator
measurement, physical-memory result, or performance result.

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
