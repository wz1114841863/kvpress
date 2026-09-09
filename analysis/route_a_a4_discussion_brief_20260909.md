# KVzap Route-A A4 discussion brief — 2026-09-09

## Purpose

This is a compact handoff for a new GPT/Codex discussion. It is not a new
experiment, architecture specification, or claim of hardware benefit. Read it
with `AGENTS.md`, `RESEARCH_CONTEXT.md`, `TRACE_SCHEMA.md`,
`KVZAP_ARCHITECTURE_PATH.md`, `analysis/route_a_research_plan.md`, and
`analysis/route_a_a0_a3_a4_handoff_20260902.md`.

## Frozen background and current policy point

- Phase 0, 45 LongBench balanced-v2 predictor-only traces, and Route-B B=4
  screening are frozen. Do not overwrite traces, freeze JSON, or old outputs.
- Route A keeps original per-(layer, KV-head) KVzap decisions. It predicts once,
  retains a regular 128-token hot window, then drops or appends mature retained
  records into per-head packed cold pages.
- Current A4 observation point: Qwen/Qwen3-8B, official MLP predictor,
  threshold `-4`, hot window `128`, page `64`, oldest-first admission budget
  `512` retained tokens/(layer, call), all 36 layers and all 8 KV heads.

## Evidence status

| Stage | Established result | Evidence class | Boundary |
|---|---|---|---|
| A0--A3 | Packed-page capacity, scheduler and branch-consistent byte/cycle feasibility at explicit candidate points. | trace-derived / modeled | Not HBM, allocator, runtime, throughput, energy, area, or hardware evidence. |
| A4.0 | Policy-on reference reads hot + pending + sealed packed cold; preserves original mask/position/append order; online merge matches same-mask dense; bypass is explicit. | functional semantic | Full-KV answer equality is not required; applicable comparator is same-mask KVzap. |
| A4.1 | Qwen all-layer/all-head external cold ownership and native-cold absence passed; dense and Route-A same-mask token digests matched in accepted fixed requests. | functional + measured Python-reference software | Python runtime/allocator/profiler do not predict hardware performance. |
| A4.1 h16/h32 | Source-elision structure was stable: 34.470% and 34.531% of three-source decisions skipped; about 1.966 and 1.964 actual partial sources per merge. | profiler-derived accounting | Fresh h16/h32 source SHA values differ and must not be falsely equated. |
| A4.2.0 | Explicit control/data interface and unresolved resource fields recorded. | observed software contract | Not architecture-spec freeze. |
| A4.2.1 | Every unresolved field mapped to a declared A3 candidate range; no candidate selected. | A4 observed + A3 modeled | No hardware calibration or sizing decision. |

## Key accepted artifacts

- A4 policy-on all-layer replay semantic gate:
  `analysis/experiments/route_a40_policy_on_qwen_all_layers_replayed_mask_01/a40_policy_on_qwen_manifest.json`
- Fresh h32 semantic pipeline:
  `analysis/experiments/route_a4165_summarization_all_layers_budget512_horizon32_semantic_02/a4165_long_horizon_semantic_pipeline_manifest.json`
- h32 three-path repeated Python-reference measurement:
  `analysis/experiments/route_a4166_summarization_all_layers_budget512_horizon32_three_path_02/a4166_long_horizon_three_path_measurement_manifest.json`
- h32 three-path profiler parent and child summary:
  `analysis/experiments/route_a4167_summarization_all_layers_budget512_horizon32_three_path_profiler_01/a4167_long_horizon_three_path_profiler_manifest.json`
  and `three_path_profiler/a4163_cross_workload_three_path_profiler_summary.json`
- h16/h32 no-model accounting:
  `analysis/experiments/route_a4168_summarization_cross_horizon_accounting_01/a4168_cross_horizon_accounting_report.json`
- A4.2.0 observed resource/interface contract:
  `analysis/experiments/route_a4200_summarization_observed_resource_contract_01/a4200_observed_resource_contract.json`
- A4.2.1 sensitivity matrix:
  `analysis/experiments/route_a4201_summarization_contract_sensitivity_01/a4201_contract_sensitivity_matrix.json`
- A3.6 sensitivity input and A3-edge candidate DSE input:
  `analysis/experiments/route_a36_govreport_n5_budget512_hardware_sweep_01/hybrid_activation_manifest.json`
  and `analysis/experiments/route_a3_qwen3_8b_edge_admission_dse_02/a3_edge_manifest.json`

## What the current software evidence says

The functional data path is real: selected cold attention is provided by
pending staging and packed pages rather than silently by native dense cold KV.
Empty pending/packed sources are explicitly skipped, while hot, packed and
merge dominate the present Python reference's profiler structure. This explains
why the reference is slower than dense software; it does not prove a hardware
slowdown or rule out a hardware implementation.

The 32-token profiler observed 76,032 merge calls. Hot made 76,032 partial
calls, packed made 72,864 partial calls and 3,168 skips, and pending made 436
partial calls and 75,596 skips. These are source/profiler accounting counts,
not hardware operation or traffic counts.

## Explicitly unresolved fields

1. Pending FIFO depth and overflow policy.
2. Page-table entry layout, allocator, and page-seal protocol.
3. Bank mapping, burst utilization, and pending gather representation.
4. Merge-state precision and the scheduler/PE placement contract.
5. Bypass switch timing and admission service/overlap behavior.

The immediate design tension is item 4: A4 requires a logical three-source
online merge, but the A3-edge candidate keeps a `(layer, KV head-group)` on one
engine and models no cross-engine merge. Neither behavior has been selected.

## Proposed next task: A4.2.2

Build a new **modeled** scheduler/merge placement comparison bound to A4200 and
A4201 hashes. Compare:

1. Co-located source service: one engine owns hot, pending, packed and merge
   for a `(layer, KV head-group)`.
2. Split-source service: sources may execute independently, then transfer an
   explicit partial-softmax state to a reduction interface.

The output should report required interface/state fields and an explicit
sensitivity grid only. It must not choose a final engine count or claim
hardware latency, HBM traffic, throughput, energy, area, PPA, RTL readiness,
or cross-model generality.

## Discussion rules

- Always label facts as **trace-derived**, **modeled**, **functional**, or
  **measured Python-reference software**.
- Full-KV bypass and same-mask dense KVzap are different controls.
- Do not overwrite existing outputs; every run needs a new directory.
- Keep model execution behind semantic/unit gates. Do not enter RTL.
