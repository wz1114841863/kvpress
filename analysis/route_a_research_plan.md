# Route A research plan: from KVzap masks to physical benefit

## Status and authority

Route A is the active research path as of 2026-08-22. The fixed-front-end
workload is the official Qwen3-8B KVzap MLP predictor, threshold `-4`, and
hot-window size `128`. The authoritative input evidence is the frozen,
predictor-only 45-request `longbench_balanced_v2` pilot
(`analysis/longbench_balanced_v2_freeze.json`). The structured Route-B screen
is frozen separately in `analysis/b4_route_b_screening_freeze.json` and must
not be overwritten or reinterpreted as a Route-A result.

Route A preserves the original per-layer/per-head token mask. It models a
hot/cold lifecycle:

```text
predict at creation -> regular hot window -> token matures -> drop or append
to a per-layer/head packed cold page list -> sealed cold pages -> sparse attention
```

The key design claim is conditional and must be tested, not assumed: packed
per-head cold pages may retain KVzap's logical compression while converting it
into physical capacity, traffic, and decode-performance benefit.

## What is already supported

The frozen v2 trace shows token-weighted logical removal `66.23%` and logical
compression `2.96x`. It also shows low token-position head sharing (keep-mask
Jaccard `0.205`, marginal-rate-adjusted excess `0.069`), so a shared-head mask
is not a safe Route-A assumption. The Route-B evidence shows the converse:
forcing block regularity reduces the compression available to a packed backend.

`tools/evaluate_kvzap_physical_layout.py` already provides a static snapshot
comparison. At page size 16, an arbitrary-token packed original-mask lower
bound is `2.9502x`, whereas timeline-position pages achieve only `1.5418x`.
This establishes a *motivation* for compaction, not a measured memory or speed
result.

Current traces contain no trustworthy decode lifecycle. They cannot establish
per-step cold admission bursts, packing writes, break-even output horizon, or
measured end-to-end performance. Those are explicit evidence gaps.

## Three falsifiable questions

### R1. Does packing amortize quickly?

For each retained KV that matures, account for hot read, cold write, metadata
update, and any tail-page allocation. Compare this one-time admission traffic
against future avoided KV reads. Report the break-even number of future decode
steps, not only a compression ratio:

```text
break_even_steps = admission_bytes / (dense_read_bytes_per_step - packed_read_bytes_per_step)
```

The equation is an accounting model. It must include only explicitly stated
traffic and must be swept over page size, context length, output horizon,
cache dtype, and bandwidth assumptions. A measured decode trace is required to
replace a synthetic admission schedule.

### R2. Is imbalance material, and does scheduling recover it?

Treat each `(request, layer, KV head)` packed page list as work. Layers remain
sequential; scheduling may only redistribute work within a layer and its ready
requests. Compare:

1. static head ownership;
2. length-aware whole-head list scheduling; and
3. dynamic page/chunk scheduling with explicit queue and partial-softmax merge
   overhead.

Report makespan, useful/idle PE cycles, utilization, P50/P95/max work per
head, queue depth, and fairness. A scheduler is justified only if it recovers a
material fraction of the static-mapping loss after its own overhead.

### R3. Does physical compression become traffic and end-to-end benefit?

Use a baseline ladder, with the same request traces and explicit parameters:

1. Full KV dense attention;
2. ideal packed KVzap (zero metadata/admission/scheduling overhead);
3. packed pages plus static scheduling;
4. packed pages plus the selected scheduler.

For each, report physical capacity, page-table metadata, hot/cold read/write
bytes, compute cycles, scheduling/merge cycles, and modeled decode latency.
Only a parameterized model can project tokens/s; only a real execution can
claim measured speed.

## Execution order and gates

### A0 — static packed-page feasibility (implementation; no model execution)

Implement a `PackedKVSimulator` that consumes frozen score/mask traces and
replays their final cold masks into append-only per-layer/head page lists for
`P in {16,32,64,128}`. It must output final capacity, tail waste, page count,
metadata, per-head length/page distributions, and a full-KV baseline. This
answers whether physical storage remains close to the packed lower bound and
supplies task sizes for scheduler simulation.

`tools/simulate_kvzap_packed_pages.py` is the model-free implementation. It
preserves the validated `final_drop_mask`, stores the trailing window regularly,
and appends each mature kept `(layer, kv_head)` stream independently into fixed
cold pages. Its scheduler handoff is `layer_head_packed_page_replay.csv`, keyed
by `trace_id`, `page_tokens`, `layer`, and `kv_head`, with
`cold_page_count`, `cold_allocated_slots`, and `tail_page_valid_slots` as the
static work descriptors. Its byte fields are declared capacity accounting only;
A0 does not establish dynamic admission, HBM traffic, allocator memory, or
performance.

### A1 — static scheduling and traffic DSE (implementation; no new model execution)

Use A0 page lists to simulate batch sizes `{1,2,4,8}` by explicitly combining
independent traces offline. Sweep PE count, page size, and scheduler policy.
Use a configurable attention page cost
`max(bytes / bandwidth, operations / throughput)` plus metadata, queue, and
merge costs. Label these workloads as simulated serving batches.

`tools/simulate_kvzap_route_a1_scheduler.py` implements this first scheduler
screen over a completed A0 directory. It uses a fixed per-`(batch slot,
kv_head)` mapping for `static_head`, LPT whole-head scheduling for
`length_aware_head`, and an LPT queue of a hot segment plus allocated cold-page
tasks for `dynamic_page`. The dynamic policy separately records declared task
dispatch and serial partial-softmax merge overhead. It supplies layer, batch,
summary, and provenance artifacts but does not yet model admission traffic or
measure any execution property.

### A2 — read-only decode-lifecycle trace (collector implementation; staged collection)

Only after A0/A1 identify a plausible Pareto region, design a separate,
non-mutating collector for generated-token predictor scores and maturity
events. It must not revive the failed stateful DMS/fake-key trace path. It
must demonstrate trace-off/trace-on output equivalence before recording:

- admissions and drops per step;
- hot-to-cold promotion bytes;
- page allocations/seals;
- cold growth;
- actual output horizon for R1.

`tools/run_kvzap_decode_lifecycle_trace.py` and
`kvpress/lifecycle.py` implement the bounded collector. They observe normal
dense-KV generation through read-only attention hooks and simulate Route-A
hot-to-cold accounting from the predictor score at token creation; they do not
run DMS or apply pruning to attention. A three-pass answer/digest gate prevents
event serialization from changing either generation or lifecycle decisions.
The manifest records phase-wise request calls/query tokens and aggregate L/H
maturity/admission/page work. It distinguishes generated-token ids implied by
the KVPress greedy loop from a decoded-text tokenizer re-count.
`tools/replay_kvzap_decode_lifecycle_pages.py` then performs a model-free
multi-page-size replay of recorded admissions, permitting P={16,32,64,128}
geometry comparisons without repeating generation. The first collection must
remain a single small request and be inspected before any expansion. Its event
bytes are declared accounting assumptions, not physical HBM or allocator
measurements.

If selected A2 samples stop before providing a useful natural decode horizon,
use `tools/screen_kvzap_a2_output_horizon.py` over an explicitly named, small
candidate set. It runs sequential normal dense-KV greedy generations, records
only answer hashes and decoded-text tokenizer lengths, and selects requests
that naturally exceed a declared threshold. It must not be used as accuracy
evidence or as a lifecycle result; re-collect each accepted request through the
three-pass A2 collector and use its observed decode-call count as the horizon.

### A3 — calibrated system model and stop/go

Calibrate byte/cycle parameters to a declared target. Route A advances only if
all three gates hold under stated assumptions:

- packed capacity remains close to original logical compression with bounded
  metadata and tail fragmentation;
- admission break-even occurs within a useful future decode horizon;
- a scheduler improves static utilization enough to offset queue/merge cost;
- net modeled read traffic and decode time remain materially below Full KV.

Failure of any gate is a design result: revise the page/scheduler architecture
before considering RTL. RTL follows only an architecture-spec freeze.

## Required provenance and conclusion boundaries

Every Route-A experiment must record source trace hashes, page size, cache
dtype and bytes/token, metadata format/bytes, PE count, bandwidth, throughput,
scheduler mode, batch construction, and all overhead constants. Keep these
labels distinct:

- **trace-derived**: mask counts, packed slots, page count, work distribution;
- **modeled**: bytes, cycles, utilization, break-even, tokens/s;
- **measured**: allocator memory, HBM counters, runtime, or hardware results.

Do not call a proxy a measurement, do not claim physical speedup from logical
compression, and do not change original KVzap pruning semantics in Route A.
