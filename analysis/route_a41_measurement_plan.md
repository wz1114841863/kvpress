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

### A4.1.2 — all-layer end-to-end decode gate

After component timing is internally consistent, measure all selected layers
for the three paired paths. Begin with `{0,18,35}`, then all 36 layers. Hold
the request, seed, decoding settings, page size, threshold, window, dtype,
model revision, predictor revision, device, and replay mask source fixed per
comparison. Record generated length and answer digest, but do not require
Full-KV answer equivalence.

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
