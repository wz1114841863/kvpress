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
