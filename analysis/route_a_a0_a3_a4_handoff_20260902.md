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
