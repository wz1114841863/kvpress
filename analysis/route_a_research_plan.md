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

### 2026-09-02 staged status (A0--A3.19)

`analysis/route_a_stage_archive_20260902.md` is the current consolidated
status archive.  Route A has passed a **conditional research-feasibility**
gate: static packed capacity is close to the original logical opportunity, and
the A2--A3 branch-consistent models identify a common positive region for
three long summarization traces under an external trusted continuation lower
bound.  It has not passed an RTL or measured-performance gate.

The next work must first establish the no-contract speculative-policy curve,
then build a semantics-checked policy-on packed-attention reference before
claiming allocator/HBM/runtime results.  The continuation contract is an
optional external control-plane interface, not a default assumption or an
output-length predictor.  When it is absent, Full-KV bypass is the strict
performance-safe mode; deferred admission remains a semantics-safe but
performance-speculative policy.

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

### A2 — read-only decode-lifecycle trace (completed evidence freeze)

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

The completed A2 evidence boundary, source artifact hashes, validated samples,
and permitted conclusions are frozen in `analysis/route_a2_lifecycle_freeze.json`.
It includes a deterministic 255-step observed decode prefix for
`longbench__gov_report__row000180`; both its 128- and 256-token-limit runs hit
their configured limits, so no natural EOS-length claim is frozen. A2 supports
the input accounting for A3, not a physical HBM, latency, throughput, or
KVzap-pruned-accuracy claim.

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

`tools/simulate_kvzap_route_a3_traffic.py` implements the first model-free A3
ledger over one or more A2 lifecycle directories and their P={16,32,64,128}
replays. The named `conservative_three` suite fixes the input set to the frozen
retrieval Qasper, reasoning 2WikiMQA, and long-horizon GovReport-row109 A2
artifacts; it is intended for cross-workload page-size Pareto scans. For
each observed `phase=decode` call it reports four baselines: Full KV; ideal
packed KVzap (hot plus logical cold tokens, zero admission/metadata/scheduler
cost); packed static-head; and packed length-aware whole-head LPT. Context and
prompt admissions are charged once before decode step one; decode admissions
are charged at the matching observed step. The two physical baselines read
allocated cold slots and page metadata under declared byte assumptions. A1 is
recorded as policy/cost provenance only: A3's selected-scheduler cycle result
is a single-request temporal model, not an A1 native-batch replay or a
measurement. It must emit per-step cumulative accounting, break-even steps,
baseline summaries, and source-hash provenance. All output is modeled.
Sweep `head_dispatch_cycles` and `scheduler_queue_bytes_per_head` explicitly;
the selected scheduler is acceptable only where it still improves the physical
static baseline after these declared overheads.
For a cross-task robustness suite, pass repeated ordered A2 lifecycle/replay
pairs to the A3 CLI; do not merge CSV files by hand or compare results with
different stated overhead points.

The next A3 sensitivity separates an offline upper bound from a potentially
online delay. `packed_oracle_*` uses the *completed* observed decode horizon to
select either Full KV for the whole request or the packed path from step one;
it is not deployable without an independently validated horizon predictor.
`packed_deferred_*` uses Full KV through N observed decode calls, then packs at
call N+1 and charges the accumulated declared admission ledger. It is intended
to test whether an online-observable delay can avoid short-horizon losses. Both
change when KVzap's mask becomes physically active, so neither is a
mask-equivalence or accuracy claim; they remain A3 modeled policy rows.
Use `--deferred-admission-decode-step-range START STOP` for a contiguous,
manifest-recorded online-delay sweep. It is specifically needed around an
observed short-horizon boundary (for example N=5,6,7 after a five-call trace),
where sparse hand-picked thresholds could conceal the relevant transition.

### A3-edge — parameterized edge-target refinement

Before architecture-spec freeze, use a candidate target descriptor (initially
`analysis/qwen3_8b_edge_target_v0.json`) rather than treating Qwen3-8B as a
universal fixed design. The descriptor records `Hq`, `Hkv`, GQA group size,
head dimension, cache bytes, window, and candidate layer-local attention
stream-engine count. `tools/simulate_kvzap_route_a3_edge.py` validates the
trace-visible dimensions and adds a declared shared admission-engine model:
memory-burst rounding, pack throughput, per-page setup and admission-engine
makespan. Its P64/P128 plus deferred-gate scan is still a model; it neither
measures a device nor validates policy-on generation. A second model must
supply its own descriptor and rerun the required A0/A2/A3-edge evidence.

The follow-on admission-engine DSE scans shared admission-engine count and
per-engine pack bytes/cycle independently (`--admission-engine-counts` and
`--admission-pack-bytes-per-cycle-points`). This isolates the design pressure
identified by the edge scan: when attention becomes faster, a fixed admission
path can dominate the modeled critical path. It is not evidence of an actual
memory controller, allocator, device latency, or throughput result.

Each DSE run also derives an architecture-constraint table from its own summary
rows. It identifies the minimum declared aggregate admission pack capacity
among the scanned configurations that preserves non-negative modeled cycles,
keeps equivalent engine/throughput decompositions, and labels unactivated
deferred policies as Full-KV fallback rather than as a capacity requirement.

### A3.5c-to-A3 bounded-service contract

`tools/simulate_kvzap_route_a3_edge.py --admission-contract-dir <A3.5c-dir>`
imports one validated schema-1.3 budgeted shadow trace per ordered A2 workload.
It consumes only the trace-derived contract: budget `B` retained tokens per
`(model-call, layer)`, layer count, K+V bytes per layer/head/token, and the
fact that the observed queue drained. It deliberately excludes host/CUDA timing
from the Python shadow reference. The emitted
`a3_edge_budgeted_admission_contract.csv` evaluates both forms of the explicit
contract over each A3 point and its Full-KV attention-cycle window `T`:

```text
per-layer parallel backend: R_layer * T >= B * KV_bytes
shared backend:             R_shared * T >= L * B * KV_bytes
```

The table compares the shared form with declared `E * P` admission capacity,
reports P50/P95/P99/worst required bytes/cycle, and retains the A3
`packed_deferred_length_aware_head` net-cycle sign at the contract's same
deferred gate as a separate screen. It is not a new
traffic/cycle resimulation: it does not prove temporal overlap, does not import
shadow timing, and does not make a sparse-attention or hardware-throughput
claim. A policy-on backend must later show how pending cold tokens are read
while its admission FIFO is nonempty.

### A3.5 — calibratable admission shadow reference

Before a policy-on sparse-attention backend, the A3.5 shadow reference reads
the normal dense cache after attention updates and writes an independent packed
cold store using the same maturity and original predictor mask decisions. Full
KV remains authoritative for generation. Its task-level timing and byte fields
calibrate only the reference gather/pack/page-table implementation on the test
device; they must not be promoted to end-to-end, HBM, allocator, throughput, or
edge-hardware claims. The mandatory guards are normal/silent/recorded answer
equality, lifecycle-digest equality, shadow semantic-digest equality, and
lifecycle/task/final-state count consistency.

### A3.5b — batched admission-submission reference

The first A3.5b increment groups all KV heads in one `(model call, layer)` into
one timed submission envelope while preserving exactly the same per-head packed
pages and lifecycle decisions. It isolates dispatch/task-granularity pressure
from storage semantics. Its grouped envelope is not a fused gather kernel and
does not establish an implementable accelerator throughput; a later deferred
gate flush and fused kernel prototype require separate validation.

A3.5b-V2 makes the per-head and per-layer-batch reference timing boundaries
explicitly comparable and can defer physical shadow writes until observed decode
step N+1. It reports planning, submit, and GPU-envelope components separately.
The deferred queue is a shadow-store experiment only; it neither changes dense
attention nor validates a packed-attention generation policy.

Cross-workload A3.5b repeats must bind to their corresponding frozen A2
lifecycle manifest. The runner validates the original JSONL request content
hash and matching model/predictor/page configuration before collection, then
requires the normal Full-KV answer hash to match the frozen A2 manifest.

### A3.5c — budgeted continuous admission

For long-horizon requests, a fixed deferred gate must not flush the complete
context backlog at once. A3.5c drains retained-position FIFOs oldest first with
an explicit per-(model-call, layer) token budget. It records burst percentiles,
queue depth, and end-of-horizon backlog. The budget is a reference workload
control, not a hardware service-rate or sparse-attention result.

### A3.6 — hybrid dense-pending + packed-cold activation DSE

The unresolved Route-A question is not aggregate B-token service alone: while
the FIFO drains, a deployable attention path must read retained cold KV from two
stores and merge their partial softmax state. Schema-1.4 of the A3.5 shadow is
opt-in through `--record-hybrid-head-progress`; it records untimed per
`(model-call, layer, kv_head)` FIFO state (packed logical/allocated/page state,
pending retained tokens, and page allocations). It still leaves Full KV
authoritative and establishes no sparse-attention equivalence.

`tools/simulate_kvzap_route_a3_hybrid_activation.py` consumes a validated A2
lifecycle and this schema-1.4 shadow. It uses the state produced strictly
before each decode call and compares three declared accounting policies:

- Full KV;
- hybrid: token-gather pending retained cold KV from dense staging plus packed
  pages already admitted, with explicit pending-index and partial-softmax merge
  byte/cycle assumptions;
- wait-for-drain: retain Full KV until the pre-call FIFO is empty, then use the
  packed-page proxy.

Admission bytes are deliberately charged sequentially in this first DSE. The
hybrid result is not a measured overlap, HBM traffic, allocator result, sparse
attention execution, or generation/accuracy result. In particular, it makes
the required dual-source and online-softmax-merge architecture cost explicit
rather than silently treating a layer-batch aggregate as per-head layout.

The A3.6 schema-1.1 DSE additionally scans three architecture boundaries
without rerunning the model: `--pending-gather-bytes-per-token-points` models
effective pending-KV read amplification from gather/burst granularity;
`--hybrid-merge-state-bytes-per-head-points` and
`--hybrid-merge-cycles-per-head-points` model online-softmax merge cost; and
`--pending-staging-capacity-tokens-per-layer-points` limits the per-layer FIFO
staging. The only initial overflow policy is explicit conservative
`layer_full_kv_fallback`: an over-capacity layer reads Full KV for that call.
These are sensitivity axes, not calibrated hardware facts.

### A3.7 — memory-system refinement and adaptive layer gate

The next two offline DSEs refine the remaining A3.6 implementation questions
without changing KVzap's mask or running a model.  The memory-system DSE
consumes the validated A2 lifecycle plus schema-1.4 head-progress shadow and
models pending retained KV as contiguous records in independent head FIFOs. It
sweeps bank count, burst size, bank service bytes/cycle, a declared mapping
proxy, and staging capacity.  Since schema-1.4 intentionally records counts
rather than token physical addresses, the result is a reproducible bank/burst
*assumption* rather than a DRAM/HBM or allocator measurement.

The adaptive-gate DSE then consumes that layer ledger and selects hybrid or
Full-KV per `(decode call, layer)` under a stated byte/cycle objective and
guard margin.  This answers whether the hybrid path needs a layer-mode control
to avoid expensive sparse gathers.  Its same-call comparison is oracle-like;
it is not an online gate implementation.  A subsequent architecture-spec or
prototype must replace it with observable, conservative features and validate
the decision error separately.

### A3.8 — observable-feature gate screen

`tools/simulate_kvzap_route_a38_observable_gate.py` performs that first
replacement without model execution.  It deliberately forbids same-call
byte/cycle values from the decision.  A pre-attention rule may only inspect
pending FIFO depth, projected maximum bank burst count from the declared A3.7
mapping, and staging overflow; it chooses hybrid only below explicit pending
and burst thresholds.  The A3.7 ledger is then used after the choice to report
agreement and regret versus the oracle gate.  Thresholds must be fixed on one
named calibration workload and evaluated on disjoint workloads before this can
be described as a deployable controller.

### A3.9 — state-consistent continue-admission gate

The preliminary A3.7/A3.8 gate comparison charged current-call admission only
on its hybrid path while retaining the canonical shadow's future packed state.
`tools/simulate_kvzap_route_a39_consistent_gate.py` repairs that ambiguity for
one implementable semantic: Full-KV is an attention-read fallback only, while
the recorded admission service continues after either choice and is charged to
both. This preserves the shadow state exactly. A different semantic,
`defer_admission`, must evolve FIFO and packed pages under every prior gate
decision; it cannot be represented exactly by schema-1.4 count-only rows and
requires a later position-preserving trace or explicitly synthetic replay.

### A3.10 — position-preserving deferred-admission input

The branch-consistent `defer_admission` model cannot reuse A3.9's canonical
shadow state after a layer chooses Full-KV. It first requires the selected
schema-1.5 A3.5 shadow profile, enabled by
`--record-deferred-replay-positions`, to retain every mature kept token's
creation position per `(call, layer, head)`. This allows a later offline
replayer to evolve each head FIFO and append-only page state after each gate
decision using the original oldest-first order. The added position CSV is
trace evidence only and can be large; collect it only for named calibration
and holdout workloads after the existing A3.9 cross-workload checkpoint.

`tools/simulate_kvzap_route_a310_deferred_replay.py` is the first consumer of
this profile. It sweeps an explicit initial Full-KV/no-service horizon and a
per-layer FIFO service budget. It uses the exact retained positions to replay
branch-specific packed-page state rather than reusing A3.9's canonical
continue-admission state. Its outputs are deliberately only a state and
admission-accounting contract for a later byte/cycle model; a favorable
conservation result does not establish sparse attention, HBM behavior, or
generation equivalence.

### A3.11 — branch-consistent deferred memory-system DSE

`tools/simulate_kvzap_route_a311_deferred_memory_system.py` is the first
byte/cycle consumer of A3.10. It differs from A3.9 by making an initial
Full-KV gate suppress both the attention-path compression and admission
service. Once activated, a staging-capacity fallback can still select Full-KV
for that call's attention read, but post-attention admission remains charged
and evolves the exact FIFO/page state. This separates the two policy meanings
without claiming an implemented sparse attention backend or measured hardware
behavior.

### A3.12 — common-hardware cross-workload gate

`tools/summarize_kvzap_route_a312_cross_workload.py` compares completed A3.11
deferred branch sweeps only when their policy and hardware points align
exactly. It records per-workload results and the minimum modeled byte/cycle
saving at every shared point; it must not select a threshold or describe a
same-workload screen as controller calibration. The next evidence gate is a
schema-1.5/A3.10/A3.11 chain for the named retrieval and summarization A2
requests, followed by this common-hardware summary.

### A3.13 — short-horizon no-admission control

The A3.12 retrieval negative result distinguishes an initial Full-KV delay
from a whole-request no-admission fallback: `defer=16` on a 17-step request
still activates service after the final attention read. Use
`tools/validate_kvzap_route_a313_short_horizon_guard.py` after replaying
`defer >= observed decode length` to prove exact Full-KV/zero-admission
degeneracy. This is a trace-known control that bounds the desired safety
semantic; it does not provide a deployable horizon prediction policy.

### A3.14 — observable request-cap contract screen

`tools/simulate_kvzap_route_a314_request_cap_gate.py` tests a limited
deployable signal: caller-provided `max_new_tokens`. A request whose cap is
below a fixed threshold remains Full-KV with zero admission; other requests
use a caller-fixed A3.11 deferred point. This can establish a conservative
API-contract policy for requests explicitly capped short, but cannot prove
protection for a request that advertises a high cap and ends early. Report its
nonnegative region separately from strict positive cycle savings.

### A3.15 — high-cap natural-early-stop counterexample

Before treating `max_new_tokens` as a sufficient deployment contract, collect
a second, independently trace-on/off-equivalent A2 lifecycle for the same
request at a strictly higher cap. `tools/analyze_kvzap_route_a315_cap_mismatch.py`
accepts the two validated lifecycle directories and rejects all changes other
than the cap. A confirmed counterexample requires that the high-cap run ends
before its cap and reproduces the reference answer hash. Only after such a
pair exists is it justified to say that a cap-only admission gate leaves a
high-cap/short-output hole and that a **lower-bound continuation contract** or
safe Full-KV fallback must be considered. This collection/analysis proves no
hardware benefit or controller accuracy by itself.

Because A3.10/A3.11 require hash-bound lifecycle provenance, freeze any new
A3.15 high-cap lifecycle with `tools/freeze_kvzap_route_a315_lifecycle.py`
into a new output directory. Never append it to, replace, or hand-edit the
existing Route-A2 freeze record.

### A3.16 — minimum-continuation contract gate

`tools/simulate_kvzap_route_a316_continuation_contract_gate.py` evaluates the
deployable semantic absent from A3.14: an external API or higher-level
scheduler declares a lower bound on the decode calls still to come. The gate
uses that declaration alone and reports Full-KV/no-admission below each
declared threshold. Observed lifecycle length is retained solely as a
post-hoc contract audit. Cross-workload conclusions require both aligned A3.11
hardware points and every supplied contract to hold; otherwise the result is a
breach sensitivity, not a feasible deployment point.

### A3.17 — cross-workload contract and policy robustness

`tools/simulate_kvzap_route_a317_contract_policy_sweep.py` jointly sweeps the
minimum-continuation gate with selected `(defer, budget)` policies. First
collect aligned A3.11 ledgers for every candidate workload; the tool rejects a
missing policy or mismatched hardware grid rather than silently intersecting
them. The next evidence goal is a common region where every contract holds,
every workload is nonnegative, and every workload admitted by the policy has
strictly positive modeled cycles. This remains a modeled robustness screen,
not a measured serving result.

### A3.18 — continuation-contract breach sensitivity

Run an aligned second A3.17 composition in which a known short request is
counterfactually assigned the long-request continuation contract. Then use
`tools/summarize_kvzap_route_a318_contract_breach.py` to compare it with the
honest assignment. This quantifies the cost of a false external declaration;
the breached audit must be explicitly marked invalid and must never be treated
as a feasible controller point.

### A3.19 — observed-prefix contract sufficiency

`tools/analyze_kvzap_route_a319_prefix_contract.py` consumes A3.11 per-step
ledgers to derive, for each policy/hardware point, the earliest observed
continuation lower bound N for which every later recorded endpoint remains
non-negative in modeled cycles. This corrects the ambiguity of using a
91/127-call final result to justify an arbitrary shorter contract. The result
is an observed-trace sufficiency bound only; it does not prove performance past
the trace horizon.

### A3.20 _ no-contract speculative deferred-admission curve

The continuation contract is not assumed in ordinary serving. Before using it
as an optional control-plane enhancement, run a dense branch-consistent
A3.10/A3.11 sweep of `defer D`, then use
`tools/analyze_kvzap_route_a320_speculative_defer_curve.py` to report final
observed-horizon saving and every cumulative observed prefix. Include the
exact Full-KV/no-admission zero reference, distinguish an unactivated
`D >= observed_horizon` policy from an activated break-even policy, and retain
negative short-output endpoints. This is a semantics-safe but
performance-speculative policy analysis; it neither makes actual length known
online nor establishes sparse-attention execution, HBM, allocator, latency, or
throughput behavior.

The first dense result is archived in
`analysis/experiments/route_a320_longoutput_speculative_curve_local_01/`: the
three long summarization traces are positive at their final observed horizons
for every `D=0..32`, while `D=16` first dips negative after activation and
recovers at calls 25--38 depending on the trace. This is deliberately not a
short-output distribution result; retain the A3.15 high-cap/early-stop
counterexample and run its dense A3.20 counterpart before drawing a
no-contract deployment conclusion.

### A4 _ policy-on reference and measurement gate

The A0--A3 closeout and A4 execution contract are in
`analysis/route_a_a0_a3_a4_handoff_20260902.md`. A4 starts with a minimum,
semantics-checked packed-attention reference, not RTL and not A3 proxy timing.
It must read regular hot KV, pending retained cold staging, and sealed packed
cold pages; merge their partial softmax states; and preserve original KVzap
mask/position semantics. It exposes an explicit Full-KV bypass and a selected
Route-A fast path; continuation information remains optional external input.

Only after A4.0 equivalence/state checks pass may A4.1 measure allocator,
profiler, and runtime behavior. A4.2 converts the validated interface into
FIFO/page/bank/merge/scheduler/bypass resource constraints. RTL remains gated
on the full A4 criteria in the handoff.

A4.2.0 first records only an observed software resource/interface contract.
It binds the explicit Full-KV bypass and Route-A fast-path behavior, three
ordered source interfaces, one merge per evaluation, and page/tail witnesses
to accepted A4.1 artifacts. It must make FIFO/PTE/allocator/bank/gather/merge
precision/scheduler/service parameters explicitly unresolved rather than
inventing a hardware size or timing from Python observations. Later A4.2 work
may bind those fields only to an explicit sensitivity range or new measurement.

A4.2.1 maps every unresolved A4.2.0 field to a declared A3 sensitivity range
only when the observed 64-token page point is included. The report must state
whether the link is A4-observed interface semantics or A3-modeled candidate
range, and must retain incompatibilities such as cross-engine merge versus
head-group placement as open contract decisions. It must not select a hardware
parameter from the range.

### A4.2.2 — scheduler/merge placement reconciliation

`tools/analyze_kvzap_route_a422_scheduler_merge_placement.py` is a no-model,
**modeled** contract study. It binds a new report to exact A4168/A4200/A4201
SHA-256 inputs and requires their source-decision/merge and policy-point
guards. It compares co-located `(layer, KV head-group)` source+merge service,
which retains A3-edge's no-cross-engine merge placement, with split-source
service. The latter exports one explicit online-softmax partial state per
non-empty hot/pending/packed source to a reduction interface and reports
declared state-payload, dispatch, transfer-work, and in-flight-state sensitivity
axes. Those axes are abstract modeled interface terms; A4168 call accounting
does not provide a service timeline, so it cannot choose a FIFO depth, PE
count, scheduler, precision, controller timing, or any hardware parameter.
The result is neither trace-derived hardware traffic nor measured runtime, and
must not claim latency, throughput, energy, area, frequency, acceleration, or
RTL readiness.

### A4.2.3 — marginal fan-in/service sensitivity

`tools/analyze_kvzap_route_a423_scheduler_merge_service_sensitivity.py`
extends A4.2.2 without pretending that aggregate profiler accounting is an
execution trace. It binds A4168/A422 SHA-256 values, proves per-source decision
conservation, and derives bounds on 1/2/3-source fan-in using only the recorded
hot/packed/pending marginals. It then compares an abstract co-located
serial-service sum with a split-source barrier-service sum over explicitly
declared work and per-logical-evaluation state-capacity axes. No source or
reducer timing, order, queue occupancy, physical FIFO, engine count, or
hardware latency is inferred. A next refinement needs a separately collected
ordered event artifact before making any queue or scheduling-placement claim.

### A4.2.4 — ordered logical source/merge event gate

`tools/run_kvzap_route_a424_ordered_logical_event_gate.py` adds an optional
recorder to the policy-on external-cold state. It is disabled by default and
cannot alter the KVzap mask or source/merge calculation. Its new gzip JSONL
artifact captures ordered logical invocations and source decisions, not service
times. A trace-off baseline, trace-on forced-token run, and trace-on independent
run bind trace enablement to same-mask semantic/ownership/replay guards. The
event order may later be paired with a separately declared service model, but
must never be read as source completion, reducer arrival, physical queue
occupancy, latency, HBM behavior, or hardware scheduling evidence.

### A4 status handoff — 2026-09-09

A4.0 semantic/state gates, A4.1 fixed-request software measurements and
profiler attribution, A4.2.0 observed resource contract, and A4.2.1 candidate
sensitivity mapping are complete for the stated Qwen3-8B policy point. The
next task is A4.2.2: resolve the scheduler/merge placement contract as an
explicit modeled comparison of co-located `(layer, KV head-group)` source+merge
execution versus a split-source execution that pays an explicit reduction
interface. It must use new output, consume A4200/A4201 hashes, keep all result
classes labeled, and must not enter RTL or claim hardware calibration.

The first A4.0 implementation is the no-model
`kvzap-route-a40-packed-attention-reference-1.0` semantic harness in
`kvpress/route_a_attention.py` and `tools/run_kvzap_route_a4_reference.py`.
It makes the Full-KV bypass and Route-A fast path explicit, preserves original
per-head keep decisions and positions while moving mature records through a
shared oldest-first pending FIFO and append-only pages, and compares stable
three-store online-softmax attention against a same-mask dense concatenation.
It is deliberately not connected to model generation yet. Passing its unit
tests permits only the next small model integration gate; it does not start
A4.1 or establish any measured result.

`tools/run_kvzap_route_a40_integration_gate.py` is that next remote-capable
small gate. It remains read-only and targets one declared Qwen3 layer/KV head:
the dense model answer must be identical with and without the hook, while each
real decode query's packed/pending/hot result must match dense attention over
the same mask-selected records. Its fresh manifest must be reviewed before
introducing an actual policy-on attention substitution. The remote command and
artifact-return contract are in `analysis/route_a4_remote_run.md`.

After that read-only gate passes, the minimum policy-on substitution is
`kvpress/route_a_policy_backend.py` plus
`tools/run_kvzap_route_a40_policy_gate.py`. It replaces the original attention
call only for one selected layer/KV-head's Qwen GQA group on `q_len=1` decode;
the group uses hot/pending/packed state and is guarded against its same-mask
dense reference. A separate budget-one run must require non-empty pending
staging. This remains an A4.0 semantic/generation gate, not a completed
A4.1 measurement: non-target heads remain dense and the runner records no
timing or allocator/profiler counter.

The immediate extension is the same runner's `--target-kv-head all` mode with
`--require-all-selected-heads-pending`: all KV-head GQA groups in one declared
layer must bypass original attention, each must numerically match its same-mask
reference, and each must read non-empty pending staging. Only after this
layer-complete gate is reviewed should A4.1 add repeated component timing and
profiler instrumentation; it must still retain separate Full-KV and same-mask
dense KVzap baselines.

The multi-layer A4.0 implementation uses one shared frozen predictor plus
independent per-layer Route-A states. It must first pass a separated
early/middle/late `{0,18,35}` semantic gate, then `target_layers=all` with all
KV heads. Each selected layer retains a mandatory same-mask FP32 guard plus an
explicitly recorded execution-dtype ULP diagnostic limit (default 16 ULP), and
explicit per-head cold/pending coverage. The all-layer Python reference is
intentionally excluded from timing claims; it is a prerequisite for, not the
A4.1 implementation benchmark.

The next A4.0 control is an independent policy-on same-mask dense KVzap
backend. It owns dense retained-cold lists rather than Route-A pending/pages,
and must prove per-layer original-mask digest equality with the Route-A pass.
Only after this paired logical baseline is accepted may A4.1 compare repeated
Full-KV, same-mask dense KVzap, and Route-A measurements.

If independently online dense and Route-A passes do not have identical masks,
the gate must stop and emit a bounded score/keep diagnostic locating the first
`(layer, KV head, position)` difference. Do not silently pair such runs as a
same-mask baseline; explicit mask replay, if later added, must be labelled as
replay rather than online predictor evidence.

The resulting paired baseline uses the dense pass as the sole online mask
source and replays those events into Route-A with exact-consumption guards.
It may isolate dense-cold versus pending/packed/hot attention semantics, but
must remain labelled `replayed-mask paired control`; retain the failed
independent-online diagnostic as the mask-stability limitation.

### A4.0 closeout and A4.1 entry (2026-09-02)

`route_a40_policy_on_qwen_all_layers_replayed_mask_01` passed the all-36-layer
replayed-mask paired functional control for the named Qwen3-8B retrieval
request. It recorded 2,016 dense and 2,016 Route-A head comparisons (36 layers
* 8 KV heads * 7 decode calls), exact mask-digest/count equality, and complete
replay consumption. Route-A exercised pending in 1,696 comparison rows and
packed pages in 1,383; its maximum FP32 comparison difference was
`1.52587890625e-05` and its maximum executed-dtype diagnostic was 13/16 ULP.
All three answer digests happened to match for this request. These are A4.0
semantic/state facts only. The independent-online diagnostic remains a
separate limitation (5 keep/drop flips in 268,992 decisions).

A4.1 work is specified in `analysis/route_a41_measurement_plan.md`. It begins
with a no-model measurement harness, then a one-layer/head component gate, and
only then a `{0,18,35}` followed by all-layer end-to-end gate. Paired A4.1
measurements compare Full-KV bypass, same-mask dense replay, and same-mask
Route-A replay; online controls are not paired performance baselines.

For a second workload, do not reuse a retrieval A4154 certificate merely
because its parameters match. A paired A4155 run must require the A4154
cross-workload provenance relay to bind the current collector event SHA-256,
all-layer/KV-head coverage, and event count through A4151. This is a source
identity guard for the repeated software measurement, not a performance or
hardware result.

The next cross-workload baseline step is a repeated three-path run: Full-KV
bypass, same-mask dense replay, and A4154-certified empty-source-elided
Route-A. It must keep the two same-mask paths bound to the current source and
their separate execution-only certificates, while recording rather than
requiring their token-digest relation. Full-KV remains the bypass control and
is not an answer-equivalence requirement. These are software distributions
only and do not establish HBM, throughput, hardware, or RTL behavior.

After the cross-workload three-path distribution is accepted, use one
separate profiler diagnostic per path to localize reference overhead. Keep
that profiler capture outside the timing distribution and require complete
Route-A source-partial-or-skip versus merge accounting. Its purpose is to bind
future A4.2 page/gather/merge contracts to observed software phase structure,
not to derive hardware timing.

For the accepted 32-token long-horizon semantic and three-path chain, repeat
that profiler step only through a provenance-bound wrapper: bind the fresh
A4165 source SHA through A4166, profile one warm-up-separated capture per
path, and retain the profiler’s coalesced phase/source accounting independently
from the repeated timing distribution. Cached offline model resolution is
permitted to avoid transient metadata fetches; it changes neither weights nor
the source replay. The output remains a Python-reference diagnostic, not a
hardware timing or traffic estimate.

Before extracting a resource contract from the accepted 16-token and 32-token
chains, produce one no-model cross-horizon accounting report. It must validate
each horizon internally but must not falsely require the independently collected
online replay sources to share a mask SHA-256. Compare only normalized
source-partial/skip/merge and page/tail witness structure, and leave profiler
range time out of the comparison.

Before extracting an A4.2 resource contract, make one no-model accounting
report that binds the accepted measurement and profiler artifacts to the same
source SHA-256 and exposes source partial/skip/merge counts per reported token.
Keep the counts trace/profiler-derived and the reset-run medians measured;
neither is an HBM or hardware-operation estimate.

Before any longer-horizon timing repetition, collect a fresh online source and
run the all-layer A4151/A4154 semantic chain at `max_new_tokens >= 32`. Do not
reuse the 16-token source by parameter substitution. This long-horizon gate is
state/semantic evidence only; it must pass before a new three-path measurement
is authorized.

The A4.1.0 implementation is `kvpress/route_a_measurement.py` plus
`tools/run_kvzap_route_a41_measurement_harness.py`. It rejects CPU timing,
uses synchronized CUDA-event and host timing, records PyTorch allocator bytes,
validates raw repetition records, and separates warm-ups from distribution
summaries. Its no-CUDA dry-run completed locally at
`analysis/experiments/route_a41_harness_dry_run_01/`; this validates only the
new-directory/schema lifecycle. The CUDA tensor-add self-check remains a
remote no-model instrumentation gate, not an A4.1 model measurement.

For the first cross-workload A3.9 screen, select a threshold pair on the
existing long-horizon GovReport calibration request, then collect matched
schema-1.4 shadows for separately frozen A2 retrieval and summarization
requests. For each evaluation workload, first run the A3.7 adaptive gate on
that workload's newly generated A3.7 memory-system directory; its manifest is
the provenance-bound cycle-oracle contract required by A3.9, and cannot be
reused from the GovReport calibration directory. `tools/summarize_kvzap_route_a39_cross_workload.py` must report both
the per-workload outcomes and the minimum result at every shared hardware
point. Short-horizon reasoning remains a negative-control workload and must
not be pooled with long-output amortization claims.

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

### A4.2.5 — ordered logical dependency schedule sensitivity

`tools/analyze_kvzap_route_a425_ordered_logical_schedule.py` consumes A424's
semantically guarded, timestamp-free logical event stream and binds A422/A423
by SHA-256. It validates continuous invocation sequence, the ordered three
source decisions, and one merge marker per event before applying a separately
declared virtual-work model. Co-located logical ownership serializes active
sources and merge per `(layer, KV head)`; split-source logical ownership exports
the explicit partial-softmax interface to a reduction dependency. Submission
spacing, source work, transfer work, dispatch work, and merge work are only
sensitivity axes. The report never maps its virtual work positions or waits to
hardware cycles, service/completion/arrival times, queues, FIFO depth, engine
count, PE count, controller timing, latency, throughput, HBM traffic, energy,
area, frequency, a selected placement, or RTL readiness.

### A4.2.6 — exact logical fan-in accounting

`tools/analyze_kvzap_route_a426_exact_fanin_distribution.py` closes the A423
marginal-fan-in ambiguity for the one A424 fixed request without inventing a
service timeline. It validates A424 gzip event accounting against its accepted
independent-run summary, derives exact 1/2/3-active-source combinations and
per-`(layer, KV head)` rows, and verifies those counts remain inside A423's
inclusion-exclusion bounds. This is no-model, timestamp-free event-structure
accounting. Exact fan-in does not establish source completion/arrival order,
queue or FIFO occupancy, engine utilization, cycles, latency, throughput, HBM
traffic, energy, area, a selected scheduler, hardware sizing, or RTL
readiness; cross-workload stability requires a separately accepted second
ordered-event source.

### A4.2.7 — cross-workload logical-event stability pipeline

`tools/run_kvzap_route_a427_cross_workload_logical_stability.py` creates that
separate source for one named retrieval request at the retained Qwen3-8B
policy point. It runs a fresh source collector, A4151, A4154, and A424 in new
child directories before comparing the accepted retrieval event stream with
the accepted summarization A424 reference. The report exposes source
partial/skip, exact fan-in, and source-combination fraction deltas without
declaring any threshold as stable or unstable. A caller cap is not treated as
the retrieval horizon: a long-cap probe chooses the child `max_new_tokens`
cap, while the semantic source records its own actual `q_len=1`
policy-decode-call count. These can differ for a multi-token question or EOS.
A4151/A4154/A424 replay-complete gates—not the wrapper—then prove exact event
consumption. This validates only fixed-
request semantic/event structure. It neither supplies source completion or
arrival time nor validates buffer occupancy, backpressure, FIFO sizing,
cycles, latency, throughput, HBM behavior, hardware selection, or RTL
readiness.

### A4.2.11 — partitioned modeled scheduler/backpressure sensitivity

`tools/analyze_kvzap_route_a4211_partitioned_backpressure_sensitivity.py`
binds A428/A429 events and compares declared global, per-layer, and per-layer/
KV-head merge placement; sequential versus cache-position logical bursts; flat
versus tree-depth fan-in work; and abstract reducer parallelism/capacity axes.
All arrivals and results are virtual-work assumptions, not observed timing or
physical queue/FIFO evidence.

### A4.2.12 — dependency-preserving source-ready/dispatch reconstruction

`tools/analyze_kvzap_route_a4212_dispatch_epoch_evidence.py` consumes the
accepted A428 event streams without loading a model or modifying Route-A.
It records the trace-derived Python-reference invocation sequence and
reconstructs forward and layer-dispatch epochs from layer resets and contiguous
`(layer, phase, cache_position)` regions. Within a layer epoch it verifies the
same KV head-group's query-head events share one source snapshot; this permits
a later model to treat them as semantically eligible for overlap after append,
but does not claim that Python or hardware actually ran them concurrently.
Layer order remains a dependency barrier. A4211 schema v2 may bind this report
and use the resulting `trace_dispatch_epoch` arrival label alongside its older
purely virtual sequential and cache-position-burst sensitivity labels. Neither
artifact selects a scheduler, reducer, FIFO, precision, PE count, or hardware
parameter, nor reports HBM, timing, latency, throughput, energy, area, or RTL
evidence.

### A4.2.13 — same-layer KV head-group sharing boundary

`tools/analyze_kvzap_route_a4213_same_layer_group_contract.py` binds A428 and
A4212 to distinguish shareable source/page-descriptor dispatch control from
non-shareable Attention state. For each same `(forward epoch, layer dispatch
epoch, KV head)` source snapshot, its distinct query heads may use one logical
dispatch description per active source; their Q-dependent source partials,
partial-softmax states, and online merges remain separate. This is a
functional/trace-derived interface boundary and accounting comparison, not a
claim of fused execution, saved traffic, cycles, latency, throughput, FIFO
occupancy, hardware selection, or RTL readiness.

### A4.2.14 — Qwen anchor core-contract closure

`tools/close_kvzap_route_a4214_core_contract.py` is the A4.2 stopping point
for the current Qwen3-8B/KVzap anchor. It hash-binds the observed A4200
interface, A4201 unresolved-range matrix, matched three-workload A428 events,
and A4211–A4213 dependency studies. The output archives a portable semantic
contract, a separately labelled Qwen-specific descriptor, and explicit
portability preconditions. It intentionally selects no hardware dimension and
does not establish cross-model/cross-algorithm portability. Later work should
use M0–M3 minimal portability gates and an envelope comparison rather than
repeat Qwen A0–A4 wholesale.

### M0 — Nous Llama 3.1 8B no-model portability provenance gate

Before a second-model semantic run, `tools/validate_kvzap_llama31_m0_provenance.py`
must create a new `kvzap-llama31-m0-provenance-1.0` manifest. It verifies the
already cached fixed-revision Nous snapshot through JSON/index metadata and
declared shard presence, derives the Linear predictor repository exactly as
`KVzapPress` does, resolves/records its revision and config hash, and requires
the JSON dimensions to agree (Llama 4096 hidden, 32 layers, 32 query heads,
8 KV heads; Linear predictor 4096 input, 8 output, 32 modules). It additionally
records whether the official predictor name agrees with KVzapPress's base-name
derivation. A mismatch is a `blocked` M0 outcome until an invocation explicitly
binds the reviewed default-off `predictor_repo_id_override` to the exact
official candidate; this does not modify the default path. It loads no base or
predictor weights. This is not a Meta-official reproduction,
functional mask, Route-A lifecycle, accuracy, traffic, latency, hardware, or
RTL result.

### M1 — Nous Llama 3.1 8B functional semantic-portability gate

`tools/run_kvzap_llama31_m1_semantic_gate.py` is the minimal runtime gate after
completed M0.  It is deliberately not the legacy DMS/fake-key path.  With the
M0-bound explicit default-off Linear predictor override, it runs one fixed
request through three controls: Full-KV bypass (zero Route-A admission), online
same-mask dense KVzap, and replayed-mask Route-A hot/pending/packed attention.
The dense pass is the one online source of original decisions; Route-A consumes
those exact events once for every one of the 32 layers and 8 KV heads.  It does
not independently re-score after its attention substitution can change later
hidden states. Each selected group must perform a q_len=1 policy
comparison and each layer must execute the FP32/executed-dtype same-mask guard.
The Full-KV, dense, and Route-A generated answers are reported by digest only
and need not be equal.  `page_tokens` and `admission_budget` are required,
declared functional-reference inputs rather than a hardware selection.
Optional pending/packed witnesses may strengthen coverage but their absence is
not silently inferred.  M1 is a one-request functional/trace-derived semantic
portability check, not an accuracy, lifecycle-envelope, HBM, timing,
throughput, energy, area, hardware, architecture-specification, or RTL result.

### M2 — Nous Llama 3.1 8B Route-A lifecycle-portability gate

`tools/run_kvzap_llama31_m2_lifecycle_gate.py` is the next minimal gate, not a
second-model A4 reimplementation. It hash-binds completed M0/M1 and reuses
M1's paired semantic relation: an all-layer/all-head dense control scores the
original mask online, then Route-A consumes that exact event stream once. Two
declared reference-state points separate lifecycle witnesses: budget one
requires hot+pending+packed state; budget 512 requires hot/packed state and a
sealed multi-page packed witness with a nonempty tail. Both retain same-mask
FP32/executed-dtype guards. Route-A state conserves each matured position and
uses append-only pages, but M2 does not free or substitute native model-cache
storage. Page/admission inputs are not hardware choices. This is fixed-request
functional/trace-derived lifecycle evidence only, not a lifecycle distribution,
accuracy, physical capacity, traffic, timing, throughput, energy, area,
hardware, architecture-specification, or RTL result.

### M3 — Qwen/Llama semantic-portability and descriptor-envelope comparison

`tools/compare_kvzap_route_a_m3_portability_envelope.py` is a no-model,
new-output comparison that SHA-256 binds the completed Qwen A4.2.14 core
contract closure with Llama M0, M1, and M2. It admits the two fixed anchors
only after their required provenance/semantic/lifecycle guards validate, then
records the shared Route-A semantic state classes separately from each model's
fixed-workload descriptor. Qwen's three-request source/fan-in/page-tail
distributions are never combined with Llama's one-request lifecycle scalar
summaries: they are inputs for a future bounded envelope study, not universal
resource ranges. M3 establishes neither a hardware dimension nor broad model
or algorithm portability. It is no-model hash-bound functional/trace-derived
comparison evidence, not capacity, traffic, timing, throughput, energy, area,
hardware, architecture-specification, or RTL evidence.

### M3.2 — archival-unit and provenance-consumption clarification

The versioned `kvzap-route-a-m3-portability-envelope-comparison-1.1` report
supersedes only the presentation of a completed M3.1 archive: it binds the
immutable M3.1 report as an input and writes a fresh directory. It labels both
`kv_heads_per_layer` and `total_layer_kv_head_state_count`, so Qwen's 36 x 8
and Llama's 32 x 8 states cannot be mistaken for a per-layer comparison or an
accelerator dimension. If raw Qwen A4.2.14 source hashes differ across hosts,
M3.2 records both hashes and rejects the run unless the canonical projection of
the fields M3.1 actually serializes or consumes agrees with the prior M3.1
report. This reconciliation establishes neither byte identity of the complete
upstream reports nor new model/workload/hardware evidence.

### M4 — bounded Nous Llama 3.1 8B workload-descriptor expansion

M4 is the first limited cross-workload step after M0--M3. It reuses the
completed retrieval M2 gate and runs the unchanged M2 functional contract once
each for the built-in summarization and reasoning requests, at the same fixed
threshold, hot window, page reference, state probes, seed, and decode cap.
`tools/analyze_kvzap_llama31_m4_bounded_workload_envelope.py` then hash-binds
the three completed M2 manifests and reports separate bounded scalar
descriptors: context length, source presence, exact-mask decision count,
page-witness count, and final Route-A state maxima. It rejects mismatched
M0/M1 provenance, mismatched functional-reference inputs, duplicate request
content, or missing M2 guards. The three requests are a coverage matrix, not a
model/workload distribution, accuracy benchmark, resource sizing range, or
hardware result. No A0--A3 numeric conclusion is transferred to Llama.

If a fixed-workload M2 run observes an execution-dtype ULP value above the
default strict limit, M4 must not silently raise that limit. The M2 CLI keeps
`--execution-dtype-ulp-mode=enforce` as its default and adds the explicit,
bounded `record_only` diagnostic mode. It retains the same-mask FP32/executed-
dtype guard work, exact online-dense-mask replay, and scalar breach summaries,
but it is explicitly not a strict numerical pass. All three M4 workload inputs
must use the same declared mode and limit; failed directories remain preserved
and are not reused.

### M4.1 — summarization ULP diagnostic closure

`tools/analyze_kvzap_llama31_m41_summarization_ulp_diagnostic.py` is a
no-model, hash-bound follow-up to a record-only M4 matrix. It binds M4 plus
all three M2 manifests, rejects missing replay/guard/provenance conditions, and
reports only bounded scalar ULP-breach samples. Each sample is paired with its
FP32 absolute difference, local values, ULP spacing, unique location count, and
declared `atol` context; retrieval/reasoning zero-breach counts are a fixed
matrix comparison, not a probability claim. A small absolute value does not
convert record-only evidence into a strict ULP pass, and no merge precision,
hardware resource, or RTL choice is made.

### M5 — Llama matched-horizon source/fan-in descriptor alignment

`tools/run_kvzap_llama31_m5_matched_horizon_workload_descriptor.py` is the
next bounded model run after M4.1. It SHA-256 binds M0/M1/M4/M4.1, including
the explicit record-only summarization ULP context, then reruns each built-in
Llama workload at the same declared eight-token cap and requires equal actual
all-layer policy-decode-call counts. A separate Full-KV bypass, online
same-mask dense source, and Route-A exact replay are retained for every
workload. Route-A enables the existing untimed logical recorder, which emits
source partial-or-skip decisions and one merge marker for every attention
invocation. M5 reports normalized source combinations, active-source fan-in,
partial record counts, and page/tail descriptors both per workload and per
`(layer, KV head)`, using fields aligned with Qwen A4.2.8.

This aligns descriptor *meaning*, not numeric distributions or hardware
requirements: Qwen and Llama retain their own fixed-workload rows. The recorder
has no source-ready/completion timestamps, so M5 cannot validate scheduler
overlap, backpressure, queue or FIFO occupancy, cycles, latency, HBM traffic,
throughput, energy, area, hardware dimensions, architecture specification, or
RTL readiness. Record-only does not relax M2's default strict guard, turn the
M4.1 observation into a strict pass, or choose merge precision.

### M5.1 — fixed-continuation horizon correction

The first M5 natural-pipeline attempt is retained when its three request event
streams show unequal actual policy-decode-call counts despite the shared cap:
the cap is an upper bound and cannot by itself create a matched horizon. M5.1
(`tools/run_kvzap_llama31_m51_fixed_horizon_workload_descriptor.py`) binds that
started record plus M0/M1/M4/M4.1 by SHA-256, and creates a new output only. It
uses a declared fixed eight-token continuation that does not stop on EOS. The
dense run provides both the original mask stream and each request's fixed token
trajectory; Route-A is forced to consume both exactly once. Full-KV runs under
the same fixed count as a separate zero-Route-A-state control. Each workload
must observe exactly seven all-layer `q_len=1` calls. M5.1 schema v1.1 retains
the existing per-attention FP32/executed-dtype same-mask guards, but does not
introduce a whole-vocabulary logits-close requirement after a deliberately
forced post-EOS trajectory: that property is not part of M1/M2's contract.

M5.1 fixes the *horizon conditioning* required by descriptor comparison. It
does not report natural generation length, quality, or serving behavior. Its
events remain timestamp-free logical source/merge observations, therefore it
does not validate overlap, scheduler/backpressure behavior, FIFO occupancy,
cycles, latency, traffic, hardware resources, architecture specification, or
RTL. The record-only ULP context stays a non-strict diagnostic; no precision
choice is implied.

### M6 — conditioned Qwen/Llama logical-descriptor coverage envelope

`tools/analyze_kvzap_route_a_m6_cross_model_fixed_horizon_envelope.py` is the
no-model next step after accepted Llama M5.1. It SHA-256 binds the Qwen A4.2.14
core-contract closure, the Qwen A4.2.8 three-workload matched-horizon report,
and the Llama M5.1 three-workload fixed-continuation report. It also binds the
completed M3.2 reconciliation report: any cross-host raw A4.2.14 core-report
hash mismatch is accepted only if the M3.2 canonical consumed projection agrees,
the raw input matches one of M3.2's two registered hashes, and both raw hashes
remain explicit. Before comparing,
it requires the completed semantic/event guards, the same declared eight-token
continuation, seven actual all-layer `q_len=1` calls, hot window 128, and page
reference 64. It keeps six model/workload rows separate and derives only
normalized source-combination/fan-in/active-source fractions, source-nonempty
conditional record-count distributions, and packed-tail distributions.

M6 then reports an explicitly named observed min/max *coverage envelope* over
those six rows. This permits later resource-contract planning to retain both
Qwen's predominantly hot+packed cases and Llama's higher observed three-source
cases without averaging either away. It intentionally rejects missing or
inconsistent descriptor fields and does not pool absolute event counts, layer
counts, or aggregate KV-head counts. The output is no-model,
functional/trace-derived comparison evidence, not a model/workload distribution,
physical capacity, traffic, queue/FIFO, scheduling/backpressure, cycles,
latency, throughput, energy, area, hardware parameter, architecture
specification, or RTL result. M4.1 remains record-only and cannot be used to
select merge precision.

### P0 — SnapKV frontend admission contract on the Qwen3-8B anchor

P0 begins the bounded cross-algorithm branch without reopening the completed
KVzap A0--A4 anchor.  The admission question is narrower than Route-A mapping:
can the frontend expose an immutable per-identity final action that a later
backend can replay?  The required contract is a terminal action for every
`(layer, KV head, original position)`, an explicit decision epoch, stable
identity/position preservation, and a same-mask comparator for the later
functional gate.  A frontend need not have KVzap's online pending state, fixed
hot window, or online-softmax merge to pass P0.

`tools/run_snapkv_route_a_p0_contract_gate.py` is initially fixed to the
frozen Qwen3-8B revision and uses `SnapKVPress` only as a score source.  Its
observer does not call the native press context manager and therefore never
replaces native cache K/V.  It records a fresh
`route-a-frontend-decision-stream-1.0` only in a new output directory.  The
stream is produced from exactly the native top-k selected set, but is ordered
by original position after selection; native score-ranked gather order is not a
canonical Route-A state order.  P0 rejects duplicate or missing identities,
inconsistent sequence lengths, nonterminal epochs, mismatched top-k counts,
and a dropped SnapKV observation-window position.  It also runs a same-seed
trace-off dense control and rejects any trace-on observer answer-digest change.

This does not assert that SnapKV has the KVzap maturity lifecycle: SnapKV is a
one-shot prefill decision source, so pending/maturity descriptors are absent by
design.  P0 is functional plus (after a model run) trace-derived frontend
evidence only.  It does not establish native SnapKV decode quality, same-mask
Route-A attention equivalence, cache capacity, traffic, scheduling,
backpressure, FIFO sizing, latency, throughput, energy, area, hardware
parameters, architecture specification, or RTL readiness.  The next required
sequence is P1 then P3 then P2.  P1 first replays the canonical stream into an
offline append-only packed-page opportunity analysis.  P3 then replays the
same stream into a bounded same-mask dense and Route-A functional reference.
Only after P3 is accepted may P2 describe lifecycle/resource fields; none of
these steps authorizes P4 resource-envelope comparison or hardware claims.

### P1 — SnapKV static packed-page opportunity

`tools/analyze_snapkv_route_a_p1_packed_opportunity.py` is the no-model step
after accepted P0. It consumes only one hash-bound completed P0 directory and
revalidates its terminal stream before constructing the explicit final mask.
The initial mapping uses exactly SnapKV's protected observation window as the
resident hot window: terminal keeps in that suffix are hot, earlier terminal
keeps form independent append-only cold streams per `(layer, KV head)`, and
terminal drops are absent. The native score-ranked gather order is never used
as position identity or append order.

P1 sweeps declared page sizes `{16,32,64,128}` and reports slot count, tail
waste, page count, and per-head distributions plus declared K+V and metadata
accounting. The resident window and byte fields are explicit mapping/accounting
inputs, not selected hardware parameters. This is a fixed-request
trace-derived static opportunity study with modeled accounting fields; it does
not establish same-mask functional equivalence, native decode quality,
admission/maturity, pending state, allocator behavior, HBM traffic,
scheduler/backpressure, latency, throughput, energy, area, architecture, or
RTL. P3 remains the next semantic gate after P1.

The completed Qwen3-8B summarization P1 source is
`analysis/experiments/snapkv_route_a_p1_packed_opportunity_qwen3_8b_01/`;
its report SHA-256 is
`f55f4a4ca9020dcbf02acce3c7f272dfafd5ecfd0bdfb2a79918015ddfd3010d`.
It hash-binds the completed P0 manifest
`c4a2ef3150197cab46508445f03c622238d93cd650b2778e5981d3b9a0927599`
and terminal stream
`1cb4a7bba15e54486b85cf0377554b5384999e11703183550bdc6809b1e7a365`.
For this one 891-position prefill, every one of 36 x 8 layer-head streams has
445 keeps: 64 hot and 381 cold. Cold packing rounds each stream to 384 slots,
leaving three tail slots. Consequently all four page-size rows have 129,024
physical slots versus 128,160 ideal slots (1.98884x versus 2.00225x relative
to the 256,608-slot full baseline); page count is respectively 24/12/6/3 per
head for P=16/32/64/128. This uniformity follows the fixed top-k count and
single input, not a model/workload distribution or a hardware page-size choice.

### P3 — SnapKV bounded same-mask semantic mapping

P3 is the required semantic gate after P1, not another static capacity sweep.
`tools/run_snapkv_route_a_p3_semantic_gate.py` hash-binds and revalidates the
completed P0 manifest/terminal stream and P1 report, including P1's P0
back-pointers, canonical original-position cold mapping, and P=64 row. It
replays the immutable terminal set for every layer/KV head without using
SnapKV's score-ranked native gather order.

P0 intentionally contains only context-prefill decisions, so P3 runs exactly
that prefill and does not invent a question or generated-token decision. It
preserves Qwen's multi-token prefill output and uses its final real prefill
query only as a read-only probe after independently constructing same-mask
dense-cold and Route-A
hot/pending/packed states. Exact replay, mask digests, numerical comparisons,
and the P1 P=64 state are all gates. The explicit P=64 / admission-budget=4096
pair drains this fixed terminal state for a functional reference; it does not
select hardware parameters.

P3 enforces the FP32 same-mask guard. Executed-dtype ULP is retained only as a
bounded scalar record-only diagnostic of reduction-order rounding; it cannot
be used as a strict ULP pass or to select merge precision.

An accepted P3 run supports only bounded semantic mapping of this source. It
does not prove native SnapKV cache/decode behavior, end-to-end generation
equivalence, accuracy, pending/maturity behavior, allocator/physical capacity,
traffic, scheduler/backpressure, latency, throughput, energy, area, hardware
specification, or RTL. P2 may follow only after P3 is accepted.

The accepted fixed-request output is
`analysis/experiments/snapkv_route_a_p3_semantic_qwen3_8b_01/`; its manifest
SHA-256 is `56cd9ca61d303be0154ec12c2934ee4b71c08332d8dc8d32c5e09ca27c73ff37`.
It revalidated P0 manifest/stream SHA-256
`c4a2ef3150197cab46508445f03c622238d93cd650b2778e5981d3b9a0927599` /
`1cb4a7bba15e54486b85cf0377554b5384999e11703183550bdc6809b1e7a365` and
P1 report SHA-256
`f55f4a4ca9020dcbf02acce3c7f272dfafd5ecfd0bdfb2a79918015ddfd3010d`.
All 36 layers and 8 KV heads consumed exactly one 891-token terminal epoch
(7,128 decisions per layer; 256,608 total). Every state matched P1 P=64:
64 hot tokens, 381 packed tokens in six pages (five full plus a 61-token tail),
and zero pending tokens per layer/head. The strict FP32 same-mask guard passed.
One executed-dtype record-only diagnostic reached 79 ULP at layer 3, KV head 6,
query head 26; the maximum associated FP32 absolute difference was
`2.9802322387695312e-08`. It is a reduction-order rounding observation, not a
strict ULP pass or a merge-precision/hardware decision.

### P2 — SnapKV lifecycle/resource descriptor

P2 is the closure step after accepted P0 -> P1 -> P3, not a further model run
or a scheduler experiment.  `tools/analyze_snapkv_route_a_p2_lifecycle_resource_descriptor.py`
accepts only those completed artifacts, recomputes all three provenance hashes,
and rejects a P3 result lacking its terminal replay, same-mask FP32,
canonical-mapping, or no-native-cache-replacement guards.  It writes a fresh
`route-a-snapkv-p2-lifecycle-resource-descriptor-1.0` report only.

Its purpose is to prevent a false lifecycle inference.  The final selection,
identity/order, protected-suffix mapping, static packed terminal state, and
bounded P3 prefill semantics are available.  Online epochs/maturity, pending
arrival/service/occupancy, generated-token continuation, native SnapKV
replacement semantics, source-ready/dispatch/completion order,
scheduler/backpressure, allocator/interface fields, and hardware metrics are
explicitly unavailable.  `unavailable` is recorded as unknown (`null`), never
as a zero-valued workload or resource observation.  In particular, P3's
zero-pending terminal materialization does not demonstrate a zero-pending
decode lifecycle.

P2 is a no-model provenance-backed classification whose inputs are
trace-derived and functional.  It is neither a new hardware model nor a
measurement, does not authorize P4 resource-envelope comparison, and selects
no FIFO/PTE/bank/burst/merge precision/PE/scheduler/controller setting.  It
cannot establish native SnapKV decode, traffic, cycles, latency, throughput,
energy, area, architecture specification, or RTL readiness.

The completed output is
`analysis/experiments/snapkv_route_a_p2_lifecycle_resource_descriptor_qwen3_8b_01/`;
the report SHA-256 is
`29835a960c9a010421bf088ad3a869c476f5c67041b0127e4395df41a7c1aa29`.
It revalidated P0 manifest/terminal stream, P1 report, and P3 manifest hashes
`c4a2ef3150197cab46508445f03c622238d93cd650b2778e5981d3b9a0927599` /
`1cb4a7bba15e54486b85cf0377554b5384999e11703183550bdc6809b1e7a365` /
`f55f4a4ca9020dcbf02acce3c7f272dfafd5ecfd0bdfb2a79918015ddfd3010d` /
`56cd9ca61d303be0154ec12c2934ee4b71c08332d8dc8d32c5e09ca27c73ff37`.
For this single 256,608-event `prefill_terminal` source it reports exactly
five available fields and eight unavailable fields; P3 has zero generated-token
forwards.  Hence static canonical mapping and bounded prefill same-mask
semantics are eligible, while decode/pending, native cache/decode,
scheduler/backpressure, and physical-resource/hardware contracts explicitly
remain ineligible.  This is the desired negative boundary, not an experiment
failure and not evidence that any unavailable workload quantity is zero.

### DMS-M0 — official trained-DMS provenance and runtime-compatibility gate

The next online-frontend branch must use the official trained checkpoint, not
silently substitute KVPress `DMSPress` or a training-free scorer.  M0 is
implemented by `tools/validate_dms_m0_official_provenance.py` and is fixed to
`nvidia/Qwen3-8B-DMS-8x` revision
`da1535fc3bfb52fa340eca692a7e4e650f98838d`.  Its default static mode checks
the expected 8x/512-window Qwen3 configuration, four indexed Safetensors
shards, and the checkpoint's custom configuration/model/attention/cache code
without importing or executing that code.

The optional `config-only` and single short `model-prefill` modes are explicit
functional runtime compatibility probes.  They use the pinned local snapshot,
perform no download or generation, and produce a fresh `blocked` manifest if
the current environment cannot run the checkpoint.  A successful load/prefill
does not prove trained-DMS accuracy, mask semantics, decode lifecycle, Route-A
compatibility, allocator behavior, physical capacity, traffic, timing,
throughput, energy, area, architecture, or RTL readiness.  DMS-M1 may begin
only after M0 has both accepted source provenance and a successful explicitly
recorded runtime compatibility probe.

#### DMS-M0 outcome — source accepted; current runtime probe blocked

The first remote M0 run is retained at
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_01/` with
manifest SHA-256
`a8b6099eaa618249ff49ef73c43fb7a8df55d2aca2eb510f8c3cd922835b655e`.
All six static source gates accepted the pinned official revision: the expected
Qwen3 DMS-8x/512 fields, four indexed readable Safetensors headers, and four
parseable custom-code files (with no custom-code execution or weight tensor
materialization during the static phase).  This is provenance evidence only.

The explicit `model-prefill` compatibility probe then imported the pinned
configuration custom code but stopped while importing the model custom code:
`ModuleNotFoundError: No module named 'flash_attn'`.  The manifest records
PyTorch `2.10.0+cu128`, Transformers `5.0.0`, `model_weights_loaded=false`,
and `generation_calls=0`.  Thus it did not load weights, execute a prefill,
or establish compatibility with the current environment.  This is a precise
dependency blocker for this runtime/probe combination, not a negative result
about DMS, Route-A, quality, decode behavior, or any hardware property.  Do
not fall back to `DMSPress`; resume M0 only in an explicitly approved,
isolated runtime that provides a compatible FlashAttention stack, then retain
that new probe as a separate manifest.

The isolated existing `debug_env` was also probed without installing or
upgrading anything.  Its recorded Python/PyTorch/Transformers/FlashAttention
versions were `3.12.13` / `2.5.1+cu121` / `4.52.4` / `2.8.3`; the static M0
gate completed at
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_debug_env_static_01/`
(manifest SHA-256
`a77bee5d89f36889a548a5c9dcd77f7dac4a5a173362eccf1efc3243a945b861`).
The separate model-prefill probe at
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_debug_env_01/`
is again `blocked`, now before checkpoint custom-code execution, by
`ImportError: cannot import name 'layer_type_validation' from
'transformers.configuration_utils'`.  Its manifest SHA-256 is
`91ac04a5d90b11090fc14cce9a325023fe35999f869d312e677c541738336f8e`.
Thus FlashAttention removes the first environment blocker but does not make
this older Transformers runtime compatible; it is not evidence about model
weights, DMS semantics, Route-A, or hardware.  The next candidate runtime
must jointly satisfy the checkpoint custom configuration's Transformers API
and the FlashAttention/PyTorch/CUDA binary interface.

#### DMS-M0 — unified `.venv` FlashAttention probe

With explicit user authorization, the shared KVPress `.venv` received the
third-party, hash-pinned
`flash_attn-2.8.3.post1+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64`
wheel.  The release SHA-256 was verified as
`35e46afd97efbbc9a1163ddf7f8acb7f32a95927ca02b0bd323a14de740c303f`
before its dependency-free installation.  PyTorch remained
`2.10.0+cu128` before and after installation, and a minimal A100 `sm_80`
FlashAttention CUDA call produced a finite output of the expected shape.  This
is a narrowly scoped software dependency/functionality check, not a hardware
latency, throughput, energy, or accelerator measurement.

The fresh official checkpoint probe is
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_venv_flash_attn_01/`
with manifest SHA-256
`d39a15f0aadbdfefc07665361d8fca8dbd449b179c6095c0ab53129565cfc125`.
It is `blocked` after importing the pinned configuration custom code, but
before weight loading, by `AttributeError: 'Qwen3Config' object has no
attribute 'pad_token_id'` under Transformers `5.0.0`.  `model_weights_loaded`
and `generation_calls` remain false/zero.  Therefore the FlashAttention
dependency is no longer the M0 blocker; the remaining issue is an exact
Transformers-5/custom-DMS configuration API incompatibility.  It is not a DMS,
Route-A, quality, decode, or hardware result, and M1 remains ineligible.

### A4.2.9 — matched split-source interface-demand accounting

`tools/analyze_kvzap_route_a429_matched_interface_demand.py` binds completed
A428 and A422 reports by SHA-256, revalidates all three A424 event hashes, and
counts modeled split-source partial-state exports and additional reduction
inputs per workload and per `(layer, KV head)`. It also reports partial record
and page/tail witness distributions. Exports are abstract interface units, not
bytes or cycles; A424 has no completion/arrival timestamps, so this cannot
select FIFO depth, scheduler, precision, hardware parameters, or RTL.

### A4.2.10 — modeled backpressure envelope

`tools/analyze_kvzap_route_a4210_modeled_backpressure_envelope.py` binds A428,
A429, and A425 by SHA-256 and sweeps declared source/reducer virtual-work
profiles with abstract state-capacity axes. It compares split-source modeled
exports, peak in-flight states, blocked exports, and virtual wait against the
explicitly zero co-located cross-engine export. These are not observed arrival
or completion times, queue occupancy, FIFO sizing, cycles, or hardware data.
The v2 contract aggregates all nonempty source partials from one logical
invocation into one fan-in merge task; its capacity axis is merge tasks, not
partial states. The v1 serial-per-partial result remains preserved but is not a
FIFO-sizing result.

### DMS-M0 — compatible isolated runtime accepted

The official DMS README specifies Transformers `4.57.3` and loads a separate
base `Qwen/Qwen3-8B` tokenizer. Accordingly, M0 model-prefill now requires an
explicit local tokenizer snapshot rather than incorrectly treating the DMS
weight snapshot as tokenizer-complete. The only mutated environment is the
isolated `debug_env`: Transformers is `4.57.3`, PyTorch remains
`2.5.1+cu121`, and FlashAttention remains `2.8.3`. A no-model static gate and
a minimal FlashAttention CUDA functionality check passed first.

The completed prefill manifest is
`analysis/experiments/dms_route_a_m0_official_provenance_qwen3_8b_debug_env_tf457_base_tokenizer_prefill_01/dms_m0_official_provenance_manifest.json`
(SHA-256 `0fda714d8f67b9c646c82788113b4e037c9e3b70ef12121b6133cb103dc7687d`).
It binds the pinned official DMS source and the supplied cached Qwen3-8B
tokenizer files, loads the weights, and completes one cache-enabled short
prefill with finite logits and no generation. M0 is therefore no longer
environment-blocked, but it proves no DMS pruning semantics, decode
lifecycle, Route-A portability, quality, timing, capacity, traffic, hardware,
or RTL property. DMS-M1 may now be designed as the next separate semantic
gate; no hardware parameter is selected.

### DMS-M1 — native decision/cache semantic observation

M1 is intentionally not a KVzap-style same-mask Route-A substitution gate:
the official trained DMS code makes binary decisions, delays their effects by
its configured window, and reuses native cache slots. The M1 observer wraps
only the inherited `DMSCache.update` call and requires a separate trace-off
execution to have identical generated-token, per-forward logit, and final
native-cache-state digests. It does not instantiate `DMSPress`, KVzap, a
Route-A backend, fake-key attention, or the generation API.

The first completed fixed retrieval instance is
`analysis/experiments/dms_route_a_m1_native_semantic_qwen3_8b_retrieval_02/`
(manifest SHA-256
`5c3e72957711c6d801667a2da0ca08720ce9e1238393b42137c1c9874a0aaa55`).
For 625 prompt tokens and four explicit decode forwards, it observes all 180
expected layer-call events (36 layers times five calls), 126,919 binary
decision-one bits, and native cache shortening in 269/288 layer-head states;
the final native lengths range from 513 to 629 versus logical history 629.
This proves only the recorded official DMS native-state behavior and that the
observer leaves that execution unchanged. It does not prove DMS accuracy or
make cache lengths physical capacity, traffic, latency, throughput, energy,
area, hardware, or RTL evidence. A subsequent DMS-M2 must explicitly decide
whether an adapter can preserve this delayed-eviction/reuse semantics; it may
not assume it is KVzap's packed-cold lifecycle.

### DMS-M2 — delayed-eviction/slot-reuse adapter-contract replay

M2 is the deliberately narrow next question after M1: can an independent
control-plane model reproduce the official DMS delayed-eviction and native-slot
reuse lifecycle without changing a native DMS execution? It is not allowed to
instantiate `DMSPress`, alter an official decision, move K/V, replace
attention, create a packed cold store, or call the outcome a Route-A mapping.
The completed M0 source/runtime manifest and M1 observer-equivalence manifest
are required inputs and their SHA-256 values are recorded.

The gate first runs one fixed request with the normal official cache and then
with a read-only observer that copies the binary decision bits only after they
have been supplied to the native update. It requires exact token/logit/final
cache-state equivalence. The result serializes a compact decision NPZ with
only decision bits and structural event delimiters. A pure-Python controller
then applies the official contract per layer/KV head: a decision labels the
preceding arrival; when that arrival reaches the delayed ring candidate, reuse
its abstract native slot; otherwise grow the native logical length. Every
native before/after cache-length vector and the final 36-by-8 vector must
match.

M1's summary hash is retained for an informational cross-run comparison, not
as an unsupported requirement that a later capture on another available GPU
have identical summary bits. M2 validates identical request provenance, and
its actual acceptance conditions are its own trace-off/on equivalence plus
per-event and final-matrix native-length agreement.

The accepted M2 run is
`analysis/experiments/dms_route_a_m2_adapter_contract_qwen3_8b_retrieval_01/`
with manifest SHA-256
`52b1445bf591948c12b8af131e3c92be4be3a9c9f73f35804b5ff77d0cfc842e`.
For the M1-bound 625-token retrieval request and four decode forwards, it
captured 180 native events and 127,047 decision-one bits. The controller agreed
with every native before/after length vector and the final 36-by-8 matrix; 269
of 288 final layer-head lengths were shorter than the 629-token logical
history, and 677 layer-head event states contained abstract slot reuse. M1/M2
summary hashes were not identical across runs; that discrepancy is explicitly
recorded rather than discarded or relabeled as a semantic failure.

This can establish trace-derived native decision/state evidence plus a bounded
functional modeled controller contract for that request. It cannot establish
semantic portability into Route-A, packed capacity, traffic, timing,
throughput, energy, area, quality, hardware selection, architecture, or RTL.
Only after this gate passes should a later, separately designed study ask what
additional state/interface would be needed for a Route-A-compatible adapter.

### DMS-M3 — active-native-slot topology precondition

M3 asks a narrower question before any adapter attention reference: can the
official DMS resident native slots be mapped back to unique logical arrival
serials under the documented delayed-eviction control rule? It binds the M2
decision stream but does not assume a later run has identical decisions. Its
own trace-off/on-equivalent official run observes only decisions, native cache
lengths, and DMS `recent_info`/cursor metadata. An independent controller must
match each event's ring metadata as well as its cache length, then exports the
final source-arrival serial assigned to every active native slot.

This is a topology/control contract, not an attention substitution. In
particular, DMS native slot order can differ from logical arrival order after
reuse; M3 makes no same-output, reordering-invariance, packed-cold, capacity,
traffic, timing, hardware, or RTL claim. Its value is to determine whether a
subsequent adapter must preserve physical resident-slot order and which logical
position metadata it would need.

The completed result is
`analysis/experiments/dms_route_a_m3_active_topology_qwen3_8b_retrieval_04/`
with manifest SHA-256
`f56816bb7998083de49ff24385f4bb5793d4445a98783c2063f328c2b3bf74a7`.
All 180 observed native events passed cache-length, complete ring-metadata, and
cursor agreement, and every final active slot maps to a unique logical source
arrival. However, 269/288 final layer-head topologies are nonmonotonic in
logical arrival serial when traversed in native physical-slot order (3,140
adjacent descents). The matching controller must preserve the official
software prefill rule that writes confirmed-eviction slots before new slots in
each chunk. This is the concrete condition a future adapter must represent;
it is not a selected physical page size or an attention-equivalence result.

### DMS-M4 — active-resident attention semantic gate

M4 asks the first functional question after M3, but is still narrower than a
Route-A adapter: can a one-source online-softmax replay over the *active native
DMS slots*, in official logical-slot/block-table order, agree numerically with
the unchanged official DMS decode FlashAttention result? It binds M0--M3 and
runs the same fixed request trace-off/on. The observer must not alter a cache
update or FlashAttention return path, and cannot serialize K/V, query,
attention, token, or text payloads.

The gate requires exact trace-off/on token/logit/final-cache agreement, fresh
ring/controller replay agreement, complete all-layer decode-call coverage, and
declared FP32 tolerances. Passing establishes only a fixed-request,
active-resident functional reference. It does not make DMS KVzap, retain
evicted K/V, make a packed cold store, justify source partition/merge, select
scheduler/precision/page/bank resources, or establish capacity, traffic,
timing, hardware, quality, architecture, or RTL evidence.

The completed fixed-request M4 result is
`analysis/experiments/dms_route_a_m4_active_resident_attention_qwen3_8b_retrieval_01/`
(manifest SHA-256
`6e4dc1eda065f440800ee29c03f65ad59502cf95c84f2408dce7ce8e6485b028`).
The trace-off/on token/logit/final-cache digests match exactly. All 144 decode
FlashAttention calls (36 layers times four decode forwards) meet the declared
FP32 `atol=rtol=0.03` guard; the recorded maximum absolute difference is
`0.0629558563`, while the mean of per-call mean absolute differences is
`0.0003103976`. The fresh 180-event control replay again agrees with native
length and ring metadata. Resident lengths span 513--629 and 269 layer/KV-head
native orders remain nonmonotonic, consistent with M3. This supports only the
need to preserve official active-slot order in a later adapter; it does not
justify source splitting, merge placement, or any physical design choice.

### Cross-frontend Commonality Study — next phase

The current Qwen A4.2 closure, two-anchor KVzap portability work, SnapKV P2,
and DMS M4 are archived in
`analysis/cross_frontend_residency_evidence_archive_20260915.md`. The next
execution plan is `analysis/cross_frontend_commonality_study_plan.md` (C0--C5).
It retains Route-A persistent-packed KVzap as the primary path and asks only
which semantic source-traversal fields are shared versus realization-specific.
It must not treat unobserved SnapKV decode state as available, convert DMS
arrival serials into unrecorded token positions, or promote page/FIFO/free-slot
state to a universal interface. No hardware parameter or RTL decision follows
from C0--C4.

### C0 — completed-artifact evidence-index gate

`tools/archive_cross_frontend_c0_evidence_index.py` is the required no-model
entry gate for the Commonality Study. It consumes the archive-named Qwen
A4.2.14, Qwen/Llama M6, SnapKV P2, and DMS M4 JSON artifacts only, verifies
their expected completed schemas, SHA-256 values named by the archive, and
literal claim-boundary guards, then writes a new
`cross-frontend-c0-evidence-index-1.0` report. It opens no raw traces or
payloads. SnapKV generated-token/decode must remain unavailable/null; DMS
remains a native active-resident source rather than a Route-A packed-cold
mapping. C0 is provenance-only and cannot select hardware parameters or
establish a common descriptor/hardware interface.

The accepted local output is
`analysis/experiments/cross_frontend_c0_evidence_index_01/cross_frontend_c0_evidence_index_report.json`
(SHA-256 `8a7636c2cce353ae1ba6099abb19861694d8789a6b23c8063825aeb88a750cc4`).
It hash-binds all four archive entries and records no raw payload opening,
runtime loading, or hardware-parameter selection. C1 may now specify descriptor
fields and availability semantics without rerunning any model gate.

### Cross-frontend C1 semantic descriptor

C1 is implemented by `tools/build_cross_frontend_c1_semantic_descriptor.py`.
It revalidates the C0 hash bindings to the Qwen A4.2.14, Qwen/Llama M6, SnapKV
P2, and DMS M4 completed manifests, then writes a fresh typed
field-availability matrix. The descriptor is semantic-only at `(model, layer,
kv_head, epoch)` grain: `identity`, `epoch`, `decision`, `visibility`,
position provenance, traversal order, attention binding, and model topology
are core; pending/pages/free slots/native block tables are frontend-specific
extensions.

C1 is no-model and creates neither a common cache format nor a hardware
interface. It must retain SnapKV generated decode as unknown and DMS literal
position as unknown, while keeping DMS arrival serial and native traversal
order distinct. C1 can prepare C2 realization adapters only; it cannot select
resources, establish a resource envelope, or authorize RTL.

For cross-host reproduction, C1 defaults to literal C0-bound paths. A fresh
staging path is eligible only with an explicit hash-preserving relocation flag
and exact C0 SHA-256 equality; the report records both paths. It cannot replace
an existing experiment output or reconcile divergent same-name artifacts.

The accepted C1 report is
`analysis/experiments/cross_frontend_c1_semantic_descriptor_01/cross_frontend_c1_semantic_descriptor_report.json`
(SHA-256 `7b37e8f0945018f6b387085ea129f10758962dd987b4d8437cb243c7a45677a7`).
It typed all eight core fields for all three frontend classes while retaining
the listed unknowns and selecting no interface or resource parameter.

A `zsy` remote replica also passed in the fresh
`cross_frontend_c1_semantic_descriptor_remote_replica_01` directory (report
SHA-256 `58a1dda80511f4f580853b0aaa32c8aa82b77133db472b315ad2adb5f839f1d0`).
It uses only byte-identical C0-bound manifest staging after a remote same-name
Qwen A4.2.14 artifact was found to have a different hash; it is provenance
reproduction, not a new model, resource, or hardware result.

### Cross-frontend C2 realization adapters

C2 is implemented by `tools/build_cross_frontend_c2_realization_adapters.py`.
It builds three frontend-specific semantic projections only after rechecking
the C1-bound source hashes. The adapter rejects any changed C1 status or an
unexplained/non-null unknown field, so it cannot turn SnapKV's absent decode
state into zero or DMS arrival serial into a literal token position.

The accepted C2 report is
`analysis/experiments/cross_frontend_c2_realization_adapters_01/cross_frontend_c2_realization_adapters_report.json`
(SHA-256 `7e14af14250b0143b37a9462bea152ce67b44cd9d227e37ae88e31ea24f43acb`).
It keeps KVzap Qwen/Llama anchors separate and preserves realization-specific
extensions. C2 is not a common cache/hardware interface, resource envelope,
architecture specification, or RTL gate; it only enables C3 comparison.

The corresponding `zsy_1` remote replica passed at
`analysis/experiments/cross_frontend_c2_realization_adapters_remote_replica_01/cross_frontend_c2_realization_adapters_report.json`
(SHA-256 `3dd5e120438db7406f02482ba74b50afaf9c8048d5c43cc9228234919e70b568`).
It reuses C1's byte-identical staging solely for cross-host provenance
reproduction and does not add a model or hardware result.

### Cross-frontend C3 commonality matrix

C3 is implemented by `tools/analyze_cross_frontend_c3_commonality.py`. It
compares only the accepted C2 projections, admitting a commonality candidate
only when all prerequisite fields are observed in every frontend. Its candidate
wording is deliberately abstract: a required traversal order is common as a
preservation obligation, not as a shared reorderable order or cache layout.

The accepted C3 report is
`analysis/experiments/cross_frontend_c3_commonality_matrix_01/cross_frontend_c3_commonality_matrix_report.json`
(SHA-256 `6d9e16d618dc9d779db60d6a408b87c3257e3aa2e33394e4c4e425032607fea0`).
It retains four abstraction-level candidates while leaving SnapKV decode,
DMS literal position, shared resource/temporal contract, and universal
multi-source composition unresolved. C3 enables C4 comparator-bound attention
study only; it is not a shared hardware/architecture or RTL gate.

The matching `zsy_1` remote replica is
`analysis/experiments/cross_frontend_c3_commonality_matrix_remote_replica_01/cross_frontend_c3_commonality_matrix_report.json`
(SHA-256 `74fc3eb42a3231904bc6762221c4ea41590c48813aa27b1267107560d8834a0f`).
It is provenance reproduction over the accepted C2 remote replica, not a new
workload or hardware result.

### Cross-frontend C4 attention primitive study

C4 is implemented by `tools/build_cross_frontend_c4_attention_primitive_study.py`.
It hash-binds C2/C3 and rechecks each frontend's already accepted comparator
and traversal assertion without loading a model or executing attention. KVzap
permits one to three ordered hot/pending/packed sources and one merge; the
bounded SnapKV and DMS evidence permits one ordered source each. C4 forbids
inventing a multi-source decomposition for those latter two frontends.

The accepted C4 report is
`analysis/experiments/cross_frontend_c4_attention_primitive_study_01/cross_frontend_c4_attention_primitive_study_report.json`
(SHA-256 `558f5a9c9c4c09c6ad9d4f4d4a562182be8e2841b10362f7b4cce6e0a158c715`).
Its candidate common primitive is frontend-bound ordered variable-length source
traversal under each frontend's comparator; it selects no cache format,
scheduler/resource contract, hardware interface, architecture, or RTL target.

The matching `zsy_1` remote replica is
`analysis/experiments/cross_frontend_c4_attention_primitive_study_remote_replica_01/cross_frontend_c4_attention_primitive_study_report.json`
(SHA-256 `6808293d0e49e34c84db9e59058407049ec788d4ac3289661204b381a6310087`).
It is provenance reproduction over the accepted remote C2/C3 chain, not a new
functional execution or hardware result.

### Cross-frontend C5 direction decision

C5 is implemented by `tools/build_cross_frontend_c5_direction_decision.py`.
It verifies the complete C0--C4 hash chain, then archives an evidence-bound
choice between Route-A persistent-packed primary path and a generic common
substrate. Its rules retain the latter only as a semantic abstraction because
the frontends do not share cache/lifecycle/order/comparator details or a
physical/temporal resource contract.

The accepted C5 report is
`analysis/experiments/cross_frontend_c5_hardware_direction_decision_01/cross_frontend_c5_hardware_direction_decision_report.json`
(SHA-256 `f7f3aec661602e5ec8febb7a43418c16cdf3dfc27e84a808a084b737d3c06fff`).
It retains Route-A persistent-packed as the research/architecture primary path.
It explicitly leaves FIFO/PTE/page/bank/burst/merge/PE/scheduler/controller
selection, architecture-spec freeze, and RTL unauthorized pending separate
Route-A resource-contract and workload-envelope/fallback gates.

The matching remote `zsy_1` provenance replica is
`analysis/experiments/cross_frontend_c5_hardware_direction_decision_remote_replica_01/cross_frontend_c5_hardware_direction_decision_report.json`
(SHA-256 `1e45e60713ce6256df33c5efb06b5db93f1ecf6a630b9de7fb916b9d730868b3`).
It validates the decision over the remote C0--C4 replica chain only; it does
not select a resource parameter or establish a functional/hardware result.

### A4.2.8 — matched-horizon three-workload logical-event stability

`tools/run_kvzap_route_a428_matched_horizon_workload_stability.py` collects
fresh summarization, retrieval, and reasoning sources at one declared cap and
requires their actual all-layer `q_len=1` policy-decode-call count to match
before running A4151, A4154, and A424 for every workload. Its no-model report
compares source combinations, fan-in, partial record-count distributions, and
packed page/tail witnesses. It records source/A424 SHA-256 values. This removes
the specific declared/observed horizon mismatch from A427, but three fixed
requests do not establish a workload distribution. No timing, queue, FIFO,
backpressure, HBM, hardware, scheduler-selection, or RTL claim is permitted.

### A4.3.0 — resource-contract / workload-envelope / Full-KV fallback gate

After C5 retains Route-A persistent-packed as the research direction,
`tools/build_kvzap_route_a43_resource_contract_envelope_gate.py` is the
minimal no-model pre-specification gate. It hash-binds the Qwen
A4200/A4201/A4211/A4214 contract chain, M6's six separately conditioned
Qwen/Llama descriptors, and A317/A318's continuation-contract and breach
records. It must retain six distinct model/workload rows, preserve Full-KV
bypass as a zero-admission/zero-cold-ownership control, and retain all five
resource parameters as unresolved rather than selected.
For the known local/remote Qwen A4214 raw-serialization difference, the gate
requires the supplied A4214 to bind its supplied A4211 hash and to be one of
M6's explicit reconciled raw hashes; this is provenance reconciliation, not
byte-identity or a new hardware result.

The output identifies next evidence needed for each resource field; it is not
a workload distribution, hardware resource envelope, parameter choice,
architecture specification, or RTL authorization. A317/A318 remain modeled
policy evidence, not controller timing, HBM, latency, throughput, or hardware
performance evidence.

### A4.3.1 — policy-on pending-staging snapshot envelope

`tools/analyze_kvzap_route_a431_policy_pending_staging_envelope.py` is the
first bounded follow-up to A4.3.0's pending-FIFO evidence gap. After each
fresh all-layer/all-KV-head Qwen policy-on semantic gate passes for retrieval,
summarization, and reasoning at the same paired-mask/budget-one reference
point, it hash-binds their manifests and summarizes pending-token state at
Route-A attention comparisons. It rejects a missing workload, changed control
inputs, absent pending witness, or a non-paired semantic run.

Its snapshots do not observe an admission arrival/completion queue, a finite
FIFO, overflow, service rate, or controller timing. Thus the output is not a
FIFO sizing result or architecture-specification gate; it only identifies
whether a later target-specific service contract needs to cover nonzero,
workload-varying pending state.

The all-layer gate retains the pre-existing contiguous logical-cache-position
contract. A rejection emits bounded scalar mismatch context only; it does not
relax the state model or produce an accepted A4.3.1 workload result.
Accepted A4.3.1 source runs must set
`--require-single-visible-cuda-device`; the manifest records the visible-device
count, `CUDA_VISIBLE_DEVICES`, and logical device name. Multi-device
`device_map=auto` is outside this Python-hook gate's accepted integration
contract. This environment guard is not a hardware-performance claim.
The accepted A4.3.1 runs also use the already established Qwen numerical
contract: the 16-ULP threshold is retained as a bounded record-only diagnostic,
while the FP32 same-mask check and quantization-aware executed-dtype close
envelope remain hard. This does not turn a large near-zero ULP count into a
strict pass and cannot select merge precision.

### A4.3.2 — policy-on lifecycle-transition envelope

`--record-lifecycle-transitions` is an explicit, default-off A4.3.2 mode of
the policy-on gate. It adds a trace-off Route-A replay and a trace-on replay
under the same dense mask events, requiring identical Route-A answer hashes and
original-mask digests. The trace records scalar pre-maturity, post-maturity,
and post-reference-service state for each layer append, including per-head
admitted tokens and page/tail state. It contains no K/V, token text, source
arrival/completion timestamp, or hardware service interval.

`tools/analyze_kvzap_route_a432_policy_lifecycle_transition_envelope.py`
requires three fresh Qwen all-layer/all-KV-head sources under the same single-
GPU and record-only/quantization-aware numerical contract. Its budget-one
transition values are functional/trace-derived Route-A reference actions, not
FIFO occupancy, drain rate, overflow, controller timing, HBM traffic, or a
hardware parameter selection.

### A4.3.3 — conditional admission/staging envelope

The next no-model study replays the three hash-bound A4.3.2 event streams as
independent layer-local scalar recurrences. It must reproduce the observed
budget-one aggregate pending state before it sweeps declared `Q` service counts
and `C` aggregate pending thresholds. This finds only conditional no-breach
regions on these three Qwen streams. It neither observes FIFO arrival or
completion nor assigns extra admissions to individual heads, so it cannot
select capacity, service rate, page size, page sealing, bank/burst behavior,
or a Qwen-specific hardware configuration. A corresponding Llama envelope
gate remains necessary before any architecture specification.

### A4.3.4 — prefill micro-event functional gate

To distinguish a retained-token burst from batch-append granularity, the
default-off trace-on reference may split only prefill into contiguous ordered
micro-events under the same replayed mask and admission policy. The batch
Route-A replay remains the trace-off comparator and must have the same answer
and mask decisions. Any observed pending/page-state change is a functional
lifecycle consequence of additional declared service opportunities, not timing
or hardware evidence. Llama requires an analogous gate before architecture
specification and no Qwen result selects a resource parameter.

### A4.3.5 — micro-event admission-quantum functional sweep

With chunk-64 A4.3.4 as Q=1 control, bounded Q=8 and Q=32 functional replays
test whether greater declared admission actions change pending/page state while
preserving the batch Route-A answer and replayed mask. These are geometric
sensitivity points, not controller-rate candidates. A page state is logical
only, and Llama remains required before an architecture specification.

### A4.3.6 — conditioned Llama micro-event admission-quantum sweep

The required Llama analogue does not copy Qwen's natural decode trajectory.
It binds completed M0/M1 and the M5.1 fixed non-EOS continuation contract,
including its retained record-only summarization ULP context, then runs the
three built-in Llama workloads separately at Q=`{1,8,32}` and chunk 64. For
each source, Full-KV, online same-mask dense, trace-off Route-A, and trace-on
Route-A must execute the declared fixed eight-token trajectory; both Route-A
paths replay the dense mask stream and forced token IDs exactly once. The
no-model closeout accepts only the nine hash-bound source manifests and rejects
cross-Q trajectory divergence, timed events, or mixed prerequisites. This tests
whether the *shape* of a functional Q sensitivity is observable on the second
KVzap anchor, not whether Qwen and Llama share a numerical envelope. It does
not convert the retained record-only diagnostic into a strict pass or select a
FIFO, page/bank/burst, controller rate, merge precision, or hardware design.

### A4.3.7 — cross-anchor Q-sensitivity closeout

Before testing a Full-KV fallback transition, a no-model report binds the
completed Qwen A4.3.5 and conditioned-Llama A4.3.6 reports. It validates the
three-workload, Q=`{1,8,32}`, chunk-64 contracts and then reports only
within-row Q=1-to-8/32 deltas plus a direction matrix for pending, logical
packed state, and logical full-page state. Qwen and Llama rows remain separate:
their different continuation conditions forbid numeric pooling, averaging, or a
unified resource envelope. The result is a falsifiable functional-state
comparison, not evidence for Q, FIFO, page/bank/burst, capacity, traffic,
timing, merge precision, or any architecture parameter.

### A4.4.0 — activation contract and benefit bypass contract

This step does not repeat A3.20's modeled question of whether a deferred
policy eventually recovers an activation dip.  It holds the declared deferred
policy fixed and tests the missing functional transition:
`FULL_KV_BYPASS -> ACTIVATING -> ROUTE_A_ACTIVE`.  Before an explicit commit
boundary, Full KV is authoritative and may retain an online predictor-decision
journal, but it must create neither Route-A logical admission state nor logical
hot/pending/packed/page/metadata state.  A request that ends before the gate
must remain pure Full KV with zero Route-A logical physicalization.

At activation, the reference hydrates history from the retained native Full-KV
prefix, partitions mature kept/drop positions, keeps the protected hot suffix,
performs one explicitly declared logical admission action, and records the
logical hot/pending/packed and page/tail split.  This supplies trace-derived
activation-burst and post-commit arrival inputs for a later resource model; it
does not select a flush service rate, FIFO capacity, PTE width, page/bank/burst
mapping, merge/PE, scheduler, controller timing, or a hardware architecture.
The native cache remains retained in this functional reference.  Capacity
pressure handling after activation (`ROUTE_A_ACTIVE -> protected/degraded`) is
intentionally a later Capacity Protection Contract, not A4.4.0.

### A4.4.1 — Qwen activation-contract anchor

Before any cross-anchor consolidation or capacity-pressure study, repeat the
A4.4.0 contract on Route-A's Qwen3-8B anchor.  Bind frozen Gate-A provenance
and the completed A4.3.5 three-workload Qwen source, retain Qwen's accepted
quantization-aware numerical guard, and use a declared fixed continuation only
to ensure both `D=8` end-before-activation and `D=1` activation branches are
observable.  The required result is contract parity, not equal activation
counts: Qwen and Llama must retain separate rows and no common hardware range
may be derived.  Only after this Qwen gate can a no-model A4.4.2 report bind
the two anchors' semantic invariants.  Capacity protection remains later.

### A4.4.2 — non-pooled cross-anchor contract closeout

The no-model closeout hash-binds completed Qwen A4.4.1 and Llama A4.4.0
reports plus their post-commit traces.  It rejects any source that lacks pure
Full-KV end-before-activation, exactly one `FULL_KV -> ROUTE_A` commit, absent
pre-commit Route-A logical state, retained native cache, post-commit numerical
guard work, or timestamp-free layer-complete decode events.  Its only shared
result is a boolean semantic-contract matrix.  Activation counts, logical
pages, pending, and packed state remain six independent rows: no averaging,
range/envelope, or hardware parameter derivation is allowed.  Passing this
step authorizes neither capacity sizing nor RTL; it only makes Capacity
Protection Contract design the next missing mode/fallback question.

### A4.5.0 — logical capacity-protection boundary replay

Before a model-on protection switch is attempted, replay the A4.4 activation
snapshots and post-commit traces under explicit logical pending high-watermark
sensitivity points. The first scope is intentionally conservative and
specified: maximum aggregate pending state of any selected layer. A crossing at
the activation boundary or before a later logical append transitions the
request one-way to `PROTECTED_FULL_KV`; the retained native cache becomes the
fallback authority, Route-A logical admission/drop stops, and re-entry is not
permitted in the bounded trace. This checks a falsifiable control-state
contract, not a FIFO implementation. The thresholds do not select capacity,
service rate, page/bank/burst, scheduler, controller timing, or hardware.

A later model-on gate must verify that this control action can be inserted
without changing the required Full-KV fallback semantics. Only after that may
a resource model study high-watermark/service interactions; neither replay
alone supplies physical capacity or overflow evidence.

### A4.5.1 — model-on layer-local protection semantic gate

Implement the smallest executable protection primitive before a resource
model: each attention-layer hook retains native Full-KV cache, hydrates
Route-A once under the A4.4 fixed continuation, and at `C=1024` aggregate
pending freezes that layer's Route-A state and uses native attention for its
current and subsequent calls. Bind the A4.5.0 `C=1024` witness per workload;
assert one-way transition, native call use, frozen `next_position`, contiguous
predictor journals, and unchanged forced Full-KV token inputs. Run Qwen and
conditioned Llama separately on one visible GPU.

The scope is layer-local. A4.5.0's request-global maximum-over-layers policy
remains a conservative control-plane counterfactual; it is not silently
implemented by a hook that cannot preinspect later layers. This gate cannot
select `C`, FIFO capacity/service, page/bank/burst, merge/PE, scheduler,
controller timing, or architecture parameters, and does not measure allocator
behavior, physical traffic, timing, performance, or hardware cost.

### A4.5.2 — request-global controller reconciliation

Before a model-on request-global fallback is attempted, perform a no-model,
hash-bound reconciliation of A4.4 activation state, A4.5.0's `C=1024`
request-global counterfactual, and A4.5.1's actual layer-local transitions.
For each anchor/workload, reject any disagreement between the A4.4 threshold
set and A4.5.1 protected-layer set. Then record the first layer-complete
observation that can latch global protection, the count of lower layers that
already completed the current activation epoch, and the non-retroactive
all-layer effect boundary at the next decode epoch.

This establishes control semantics only. It does not implement a global
controller, controller barrier/broadcast, or next-epoch native fallback; it
does not select C/FIFO/service/page/bank/burst/merge/scheduler parameters or
measure any latency, traffic, capacity, or hardware cost. A later A4.5.3
model-on gate must implement precisely this next-epoch scope before any
resource contract treats request-global protection as executable.
The model-on gate must declare offline cached-artifact loading before the
Transformers/HF libraries initialize; a cache miss must fail explicitly rather
than causing a network-dependent rerun or provenance substitution.

### A4.5.3 — model-on next-epoch request-global protection semantic gate

Implement the A4.5.2 controller scope without retrospectively changing the
activation epoch. Each layer reports its post-hydration, pre-append aggregate
pending state to one request-scoped coordinator. The first `pending >= C=1024`
observation latches the request; only after every ordered layer completes that
same activation epoch does the coordinator commit an all-layer native Full-KV
fallback at the following `q_len=1` decode epoch. A current-epoch local crossing
retains the A4.5.1 layer-local behavior; its Route-A state freezes immediately,
while the global action must neither reroute earlier layers nor freeze a
non-crossing layer until the next epoch.

The runner must hash-bind the A4.5.2 reconciliation and its A4.5.1 sources,
exercise separate Qwen and Llama fixed continuations on one visible GPU, and
assert the ordered observations, latch layer, next-epoch boundary, native
fallback on every layer, frozen Route-A state, no re-entry, and unchanged forced
Full-KV inputs. This is functional control-semantics evidence only. It is not a
controller implementation suitable for timing closure and does not measure or
select FIFO capacity/service, page/bank/burst, merge/PE, scheduler, latency,
traffic, throughput, energy, area, architecture parameters, or RTL.

### A4.5.4 — protected Route-A shadow-state disposition semantic gate

The next missing condition is whether request-global fallback can actually
make its non-authoritative Route-A reference state inaccessible. At the A4.5.3
next-epoch boundary, snapshot each layer's logical hot/pending/packed/page
state, then replace that state with a fail-closed tombstone while retaining
native Full-KV as the sole authority. Continue the bounded fixed horizon and
reject any Route-A shadow read, append, admission, drop, re-entry, altered
forced Full-KV token input, or native-cache mutation. This establishes only
logical reclaimability of the Route-A shadow, not a physical release.

Bind completed A4.5.3 Qwen/Llama reports and their A4.5.2/A4.5.1 source chain
before model load. Keep Qwen and Llama separate; require the same ordered
controller observations and local trigger sets as A4.5.3. The recorded state
inventory is scalar functional-reference state, not bytes, physical pages,
allocator behavior, HBM/DMA traffic, bursts, FIFO occupancy/capacity, service
rate, overflow, timing, latency, throughput, energy, area, or a hardware
parameter. A passing tombstone gate is a prerequisite to later fallback
dual-residency/workload-envelope modeling, not that model or an RTL decision.

### A4.6.0 — Route-A-active long-horizon steady-state gate

With A4.5 Full-KV-backed exit closed as a candidate protection upper bound,
return to the required normal path. Hash-bind A4.4.2 activation semantics and
run each anchor/workload under one fixed 64-token continuation: one native
Full-KV prefix decode commits Route-A, then every remaining decode call must
remain Route-A active. Full-KV supplies only the fixed token-input reference;
the active branch may not enter protection or fallback. Record timestamp-free
post-commit logical lifecycle transitions and separately analyze the final 32
decode append opportunities per layer/KV-head for sustained non-decreasing
pending-growth witnesses.

This is a bounded functional/trace-derived normal-path check, not proof of
indefinite stability. Lifecycle opportunities have no arrival/service time,
FIFO occupancy/capacity, overflow, controller timing, or physical interpretation.
It selects no service rate, FIFO/page/bank/burst/merge/PE/scheduler parameter
and reports no traffic, latency, throughput, energy, area, architecture, or RTL
result. Qwen and Llama remain separate. A failure or tail-growth witness routes
the next study to Route-A-native protection; a pass permits a later explicit
resource-model service-envelope study.

### A4.6.1 — source-separated activation-burst logical envelope

After a passing A4.6.0 finite normal-path gate, do not infer a FIFO, bandwidth,
or controller rate. First hash-bind A4.4.2 and the completed Qwen/Llama A4.6.0
reports, then retain each anchor/workload separately and split its
timestamp-free lifecycle into two sources: (1) the activation-commit
all-layer/all-KV-head logical inventory and (2) the subsequent `q_len=1`
append-opportunity inventory. Recheck trace hashes, complete layer/head
coverage, and exact pending/packed conservation. Report distributions over the
recorded logical rows, including mature-kept, pending, admitted, packed, and
logical-page state, without numerically pooling anchors.

This makes the activation peak and subsequent steady-state arrivals explicit
inputs to a later resource model; it is not that model. Counts in this stage
are neither physical bursts nor FIFO occupancy/capacity, service rate,
overflow, allocation, traffic, bytes, HBM/DMA activity, timing, latency,
throughput, energy, area, an architecture specification, or RTL evidence. A
later model must introduce its own explicit service/backing assumptions before
using these inputs to study capacity protection or net benefit.

### A4.6.2 — multi-horizon logical admission-service envelope

Do not reduce the activation question to whether one quantum clears the fixed
62-opportunity continuation. Bind the completed A4.4.2/A4.6.0/A4.6.1 chain and
model every anchor/workload separately across drain horizons
`{1,2,4,8,16,32,62}`. Initialize each `(layer, KV-head)` from its activation
pending state and replay only the post-commit mature-kept arrival sequence.
For every horizon, find the minimum declared logical service quantum that
drains the bounded prefix, and retain each head's initial/peak/final backlog,
service grant, first/terminal drain opportunity, and reaccumulation state.
Report layer-local completion and service/peak spread as the fairness contract.

Use independent per-stream service only as an optimistic no-competition bound.
Use a separately named per-layer shared policy with an explicit allocation rule
to expose head competition; the initial rule is unit-token round-robin among
nonempty heads. Neither policy is a scheduler implementation. Logical quantum
must not be translated into cycles, FIFO depth, bandwidth, HBM traffic, or a
hardware parameter. This is modeled logical backlog sensitivity, bounded by the
recorded trace horizon, and becomes an input to later physicalization-cost and
attention/admission-contention DSE—not that DSE, a net-benefit conclusion, or
a Route-A-native protection implementation.

### A4.6.3.0 — physicalization mapping contract

Before any attention/admission contention model, map A4.6.2 logical service
work to physicalization inventory under explicit alternatives. Hash-bind the
whole A4.4.2--A4.6.2 chain and recheck every A4.6.2 head's granted/final pending
state. For candidate page sizes `{16,64,128}`, report per-head KV payload
source-read/write token units, page fills/seals/tail, page-table/PTE records,
position-metadata records, and candidate dual-source merge-state records.

The mapping must name when payload movement occurs. The initial sensitivity
contains eager copy on each logical service action and sealed-page copy with an
explicit unsealed-tail reference; it must never silently call a logical
maturity/admission/page event a transfer. The output is modeled work inventory,
not measured traffic or a chosen page/PTE/metadata implementation. Only after
this contract is reviewed may A4.6.3.1 place its work alongside continuous
attention under declared arbitration policies.

### A4.6.3.1 — aggregate attention/admission contention envelope

Consume every named A4.6.3.0 variant before selecting no mapping/page point.
Under explicit abstract cost profiles, retain continuous source traversal and
merge work separately from admission physicalization work; report the bounded
horizon requirements for admission-isolated, attention-first, and reserved
admission shares. This is an aggregate sensitivity only: do not claim temporal
controller behavior, bandwidth, cycles, or an updated per-head backlog. A later
temporal contention model must recompute those states before a resource contract
or net-benefit conclusion is permitted.

### A4.6.3.2 — temporal abstract contention replay

Build on the A4.6.3.0 named mapping inventory, but do not reinterpret the
A4.6.3.1 aggregate envelope as a controller result. For layer-shared A4.6.2
points at horizons `{8,16,32,62}`, replay every opportunity with explicit
`A_t^attn`, mature-kept `A_t^new`, pending `B_t`, logical grant `G_t`, and
`B_{t+1}=max(0,B_t+A_t^new-G_t)`. Map every realised grant through the named
eager-copy or sealed-page-with-tail-reference assumption, retaining payload,
page/PTE, position, merge, and endpoint-tail inventories separately.
Dual-source merge is counted at most once per layer/KV-head after the complete
opportunity's grants, matching the A4.6.3.0 post-service state contract.

Compare strict attention-first, non-borrowing hard reservation, a
work-conserving minimum guarantee, and a simple bounded-horizon
backlog/deadline-aware sensitivity. Record aggregate and per-head peak/final
backlog, terminal drain/censoring, deadline miss, grant spread, reservation
idle/attention borrowing, and abstract admission work beside the retained
attention-source traversal demand. The deadline-aware policy may see the
recorded future only as an offline sensitivity; it is not an online scheduler.
All outcomes remain timestamp-free modeled work: they choose no scheduler,
FIFO, bandwidth, page/bank, controller, or hardware parameter, and they are
not measured traffic, timing, latency, throughput, energy, area, net benefit,
or RTL evidence.
