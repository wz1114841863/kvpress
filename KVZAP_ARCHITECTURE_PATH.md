# KVzap Architecture Research Path for Codex

## 1. Purpose

This document defines the recommended architecture-oriented research path for extending KVzap after the official implementation has been reproduced successfully. The reproducibility, Route-B evidence, and active Route-A contract are frozen in `AGENTS.md`, `analysis/b4_route_b_screening_freeze.json`, and `analysis/route_a_research_plan.md`; those records take precedence over historical suggestions below.

The goal is **not** to redesign or retrain the KVzap predictor. The goal is to preserve the original KVzap pruning semantics and design a dedicated architecture that converts KVzap's fine-grained, per-head, variable-length logical pruning into efficient physical KV-cache storage and execution.

The current direction is motivated by the trace analysis already completed:

- KVzap achieves high logical KV compression.
- The original keep/drop mask is not naturally suitable for large uniform token blocks.
- Cross-head mask similarity is low.
- Large blockification significantly reduces compression efficiency.
- Per-head capacity bucketing retains almost all of the original logical compression.
- Layer/head capacity profiles are non-uniform and require quantified scheduling analysis; the amount of recoverable utilization loss is not yet established.

The current main hypothesis is:

> KVzap's token-level pruning lacks sufficient regularity for direct coarse-grained block mapping, but the retained KV entries can be reorganized with very low capacity loss into per-head packed fixed-size pages. A dedicated architecture can therefore preserve the original pruning decisions while using streaming admission, variable-length page management, and load-balanced attention scheduling to convert logical compression into physical memory, bandwidth, and throughput gains.

---

## 2. Research Scope

### 2.1 Main research target

Design a dedicated KV-cache execution subsystem with three primary responsibilities:

1. **KV Admission / Packing**
   - Keep the original KVzap token-level keep/drop decision.
   - Convert retained KV entries into densely packed physical storage.

2. **Variable-Length Page Management**
   - Maintain a separate packed cold-cache stream for each layer/head.
   - Use fixed-size physical pages, while allowing different layer/head pairs to own different numbers of pages.

3. **Load-Balanced Attention Scheduling**
   - Handle the severe workload imbalance caused by different per-head retained KV lengths.
   - Explore scheduling at head, page, or page-range granularity.

### 2.2 Explicit non-goals

Do not make the following the main research contribution:

- retraining KVzap predictors;
- redesigning the KVzap MLP/Linear predictor;
- designing a generic GEMM accelerator for the predictor;
- forcing the original mask into large token blocks;
- directly sharing one mask across KV heads;
- building a complete LLM NPU from scratch;
- changing KVzap pruning semantics before sufficient validation.

The architecture should treat the official KVzap predictor as a fixed front-end workload.

---

## 3. Current Experimental Evidence

The latest analysis has already narrowed the design space.

### 3.1 Capacity bucketing is promising

Using the original per-layer/per-head cold KV capacity and rounding it upward to fixed token granularities gives approximately:

| Capacity granularity | Physical compression | Extra capacity fragmentation |
|---|---:|---:|
| 16 tokens | ~2.97x | ~0.57% |
| 32 tokens | ~2.96x | ~1.18% |
| 64 tokens | ~2.92x | ~2.44% |
| 128 tokens | ~2.85x | ~4.94% |

The original logical compression is approximately 2.99x.

This strongly suggests:

> It is unnecessary to regularize the pruning mask itself. Regularizing only the **physical capacity allocation** preserves nearly all of the original compression benefit.

### 3.2 Large token blocks are not promising

Direct keep-any block layouts substantially reduce compression:

- B=4: ~2.01x
- B=8: ~1.75x

Strict B=4 coalescing with margin 0 nearly eliminates mixed blocks, but the logical deletion ratio falls from ~66.23% to ~49.22%.

B=8 is worse.

Therefore, large token-block pruning should not be treated as the main direction.

### 3.3 Head-shared masks are not promising

The excess cross-head keep-mask similarity is only about 0.069.

This indicates that different KV heads preserve substantially different token positions.

Therefore, direct shared-head masks should not be a primary design assumption.

### 3.4 B=4 Route-B branch is frozen as a conditional fallback

B=4,m=0 and B=4,m=+0.25 completed bounded actual-DMS screening and a 45-trace
page-layout model; the authority is `analysis/b4_route_b_screening_freeze.json`.
The +0.25 candidate has `53.22%` token-weighted logical deletion and can reduce
timeline-page capacity/read proxies by about 5--8%, but it neither matches the
original arbitrary-token packed lower bound nor reduces observed page-count
tail metrics. Its 9-request screening is not official LongBench accuracy.

Do not expand this branch by default. Revisit it only if Route A cannot supply
token compaction or a later system DSE shows a clear Route-B Pareto advantage.

---

## 4. Proposed Architecture

The conceptual dataflow should be:

```text
                    Transformer Layer
                          |
                    Hidden State
                 +--------+--------+
                 |                 |
               Q/K/V          KVzap Predictor
                 |                 |
                 |              score[h]
                 |                 |
                 +--------+--------+
                          |
                     Hot / Recent KV
                       window=128
                          |
                  token leaves window
                          |
                    stored KVzap score
                     /            \
                  DROP            KEEP
                                    |
                                    v
                         +-------------------+
                         | Admission / Packer|
                         +---------+---------+
                                   |
                                   v
                        Per-head Packed Cold KV
                        fixed-size physical pages
                            16 / 32 / 64 / 128
                                   |
                         +---------+---------+
                         | Page Metadata     |
                         | + Page Allocator  |
                         +---------+---------+
                                   |
                                   v
                          Dynamic Scheduler
                                   |
                                   v
                         Attention PE Cluster
                                   |
                                   v
                        Partial Softmax Merge
                        (only if required)
```

Important principle:

> The keep/drop decision remains token-level and head-specific, but the physical cold-cache layout becomes packed and page-based.

---

## 5. Hot/Cold KV Model

### 5.1 Hot KV

KVzap keeps the recent sliding window, currently 128 tokens.

New KV entries should first be written to a regular hot-cache structure.

Properties:

- fixed recent-window capacity;
- regular address layout;
- no fine-grained physical deletion while still hot;
- corresponding KVzap scores must remain available until the token matures.

### 5.2 Cold admission

When a token leaves the recent window:

```text
if score < threshold:
    discard KV
else:
    append KV to the cold packed stream for this layer/head
```

For decoding, this is primarily a **streaming conditional append**, not a large global compaction operation.

This significantly reduces implementation complexity.

### 5.3 Prefill

Prefill is different because many prompt KV entries exist simultaneously.

For the first architecture version:

- preserve the original KVzap semantics;
- model prefill post-attention compression as a bulk packing operation;
- do not move pruning before attention unless a separate algorithmic accuracy study justifies it.

The decoding path should be the primary hardware implementation target.

---

## 6. Packed Per-Head Page Organization

Each `(layer, kv_head)` pair owns an independent cold-cache page list.

Example with page size `P=32`:

```text
Layer 10 / KV Head 3

Page 0 : 32 valid
Page 1 : 32 valid
Page 2 : 32 valid
...
Page 8 : 32 valid
Page 9 : 17 valid + 15 free
```

Use an **append-only page design**.

Do not implement a growing contiguous buffer that requires copying old data whenever capacity expands.

For a retained cold length `N`:

\[
num_pages = ceil(N / P)
\]

Only the final page may contain unused capacity.

For each layer/head:

\[
0 \le waste < P
\]

This is the key reason small page sizes preserve almost all logical compression.

---

## 7. Required Metadata Model

The simulator should explicitly model metadata rather than only use a capacity formula.

Suggested structures:

```text
HeadDescriptor:
    page_count
    tail_page_id
    tail_valid_count
    total_valid_tokens

PageDescriptor:
    physical_page_id
    valid_count
    next_page_id or page-list index

Global:
    free_page_queue
```

Optional fields should be added only when the implementation requires them.

A critical correctness check is whether the existing KV implementation requires original logical token positions after compaction.

Codex must inspect the current code path and determine:

- whether cached keys already contain RoPE-position information;
- whether attention later requires original position IDs;
- whether compacted cold KV needs an auxiliary position array.

Do not assume the answer.

---

## 8. Validation Stage A: Packed-Page Feasibility

Before designing RTL, build a real packed-page simulator.

Suggested component:

```text
PackedKVSimulator
```

It should replay real KVzap traces and maintain page state over time.

At minimum support:

```text
page_size in {16, 32, 64, 128}
```

For every request, layer, and KV head, report:

- logical retained KV count;
- physical allocated KV slots;
- number of allocated pages;
- tail-page occupancy;
- internal fragmentation;
- metadata bytes;
- page allocation count;
- page allocation rate over decoding time;
- cold-cache bytes;
- hot-cache bytes;
- total physical KV bytes.

Do not report only final-state capacity. Report dynamic behavior over decoding time.

---

## 9. Validation Stage B: Streaming Admission Cost

Replay real decoding traces.

For every decode step, determine which token leaves the recent window and whether it is:

- dropped;
- admitted into cold cache.

Record:

- number of new cold admissions per step;
- admission burst distribution;
- page-boundary events;
- new-page allocations;
- hot-KV read bytes;
- cold-KV write bytes;
- metadata-update traffic;
- cold-cache growth over time.

Important output:

\[
\Delta N_{cold}(t)
\]

The architecture needs to know whether cold admission is smooth or bursty.

### 9.1 Promotion / admission traffic

For each retained KV entering cold cache, explicitly account for:

- read from hot storage;
- write to packed cold storage;
- metadata update.

If KV head dimension is `D` and element size is `b`, K+V movement per token is approximately:

\[
2Db
\]

Do not assume this cost is negligible.

---

## 10. Validation Stage C: Break-Even Analysis

The architecture only makes sense if one-time packing/admission cost is amortized by reduced future KV reads.

Compute a break-even metric.

Conceptually:

\[
N_{BE}
=
\frac{one\_time\_admission\_cost}
{saved\_KV\_traffic\_per\_future\_decode\_step}
\]

Report break-even versus:

- context length;
- output length;
- pruning threshold;
- page size;
- model;
- batch size.

Desired evidence:

> Cold admission cost is amortized after only a small number of future decoding steps.

If break-even is extremely long, the architecture must be reconsidered.

---

## 11. Validation Stage D: Workload Imbalance

The trace already suggests strong layer/head imbalance.

Turn this observation into explicit architecture metrics.

For each layer:

\[
CV = sigma(N_h) / mean(N_h)
\]

and:

\[
I_{max} = max(N_h) / mean(N_h)
\]

where `N_h` is the retained cold KV length for head `h`.

Also report:

- P95/P50 head length ratio;
- max/min head length;
- number of cold pages per head;
- imbalance over decode time;
- imbalance across requests.

Most importantly, translate imbalance into simulated PE utilization.

---

## 12. Scheduler Design-Space Exploration

Do not assume page-level dynamic scheduling is automatically optimal.

Implement and compare at least three scheduling models.

### 12.1 Baseline: Static Head Mapping

Example:

```text
PE0 -> KV Head 0
PE1 -> KV Head 1
...
```

Purpose:

- quantify how much variable-length KV hurts a simple mapping.

Report:

- total cycles;
- useful PE cycles;
- idle cycles;
- utilization.

### 12.2 Candidate: Length-Aware / Bucketed Head Scheduling

Group or order heads according to workload length.

Possible buckets:

```text
0-256
257-512
513-1024
1025+
```

This keeps one head as the scheduling unit and avoids cross-PE partial softmax merging.

If this recovers most utilization, it may be preferable to page-level scheduling.

### 12.3 Candidate: Page / Chunk-Level Dynamic Scheduling

Represent tasks as:

```text
(request, layer, kv_head, page)
```

or:

```text
(request, layer, kv_head, page_range)
```

Multiple PEs dynamically pull tasks.

This provides the strongest load-balancing capability.

The simulator must quantify whether the extra scheduling and reduction overhead is justified.

---

## 13. Attention Cost Model

A realistic cycle model must explicitly account for memory and compute.

At minimum:

\[
T_{page}
=
max(
bytes_{page}/BW,
ops_{page}/Throughput
)
\]

Then include:

- QK computation;
- AV computation;
- online softmax;
- metadata lookup;
- scheduler delay;
- admission overhead;
- partial-result merge overhead;
- HBM traffic.

Total modeled time should conceptually include:

\[
T_{total}
=
T_{KV-read}
+
T_{attention-compute}
+
T_{metadata}
+
T_{scheduler}
+
T_{admission}
+
T_{merge}
\]

Do not use the shortcut:

```text
66% KV removed -> 3x attention speedup
```

The simulator must expose the gap between logical compression and actual execution speed.

---

## 14. Partial Softmax Merge Design

Page-level parallelism may split one attention head across multiple PEs.

For each page/chunk, compute local statistics:

\[
m_b = max_i(z_i)
\]

\[
l_b = sum_i exp(z_i - m_b)
\]

\[
o_b = sum_i exp(z_i - m_b) v_i
\]

These partial results can be merged using online-softmax composition.

Two architecture options must be compared.

### 14.1 Simpler option: Head-Level Ownership

All pages of one head stay on one PE.

Advantages:

- no cross-PE merge;
- simpler RTL;
- simpler dependency tracking.

Disadvantage:

- very long heads remain difficult to balance.

### 14.2 Full option: Cross-PE Page/Chunk Parallelism

Pages from one head may execute on different PEs.

Requires:

- partial result buffer;
- merge/reduction unit;
- completion tracking;
- scheduler dependency management.

Only implement this in RTL if cycle-level simulation shows a meaningful gain over simpler head-level or length-aware scheduling.

---

## 15. Page Size Design-Space Exploration

Current capacity evidence suggests:

- 16: best capacity efficiency;
- 32: very small fragmentation with half as many pages as 16;
- 64: slightly worse capacity but fewer metadata/scheduling events;
- 128: likely too coarse, but keep as baseline.

Codex must not hard-code 32 as final.

Sweep:

```text
P in {16, 32, 64, 128}
```

Measure:

- physical compression;
- fragmentation;
- page count;
- metadata bytes;
- allocation frequency;
- scheduler task count;
- HBM transaction size;
- average burst efficiency;
- number of partial softmax segments;
- queue pressure;
- total cycles.

Choose the final page size from the Pareto frontier.

---

## 16. Multi-Request / Batch Evaluation

Single-request traces are insufficient for final scheduler evaluation.

At minimum construct simulator workloads for:

```text
batch_size in {1, 2, 4, 8}
```

If necessary, combine independently collected real traces offline.

Clearly label such combinations as simulated serving workloads rather than native batched model executions.

Measure:

- task-pool size;
- static utilization;
- dynamic utilization;
- queue depth;
- HBM bandwidth use;
- latency;
- throughput;
- request fairness.

Dynamic scheduling may become more useful when multiple requests increase the available task pool.

---

## 17. Required System Baselines

Final architecture evaluation should include at least:

### 17.1 Full KV

- dense KV layout;
- conventional attention execution.

### 17.2 Ideal KVzap

Assume:

- original KVzap logical pruning;
- perfect packed physical storage;
- zero metadata cost;
- zero admission cost;
- perfect load balancing.

Purpose:

> establish the theoretical upper bound.

### 17.3 Packed KVzap + Static Scheduling

- fixed-size packed pages;
- real fragmentation and metadata;
- static head mapping.

Purpose:

> separate storage benefit from scheduling benefit.

### 17.4 Packed KVzap + Length-Aware Scheduling

- packed pages;
- length-aware head scheduling.

### 17.5 Packed KVzap + Dynamic Page/Chunk Scheduling

- packed pages;
- dynamic tasks;
- include scheduler and merge overhead.

This baseline hierarchy is essential for explaining where performance gains come from.

---

## 18. Remaining Algorithm-Side Validation

The architecture mainline should preserve the original KVzap mask.

However, close the structured-mask branch experimentally by evaluating:

```text
B=4, margin=0
B=4, margin=+0.25
```

Run real accuracy benchmarks.

The purpose is to support a final conclusion such as:

> Direct mask structuring sacrifices too much compression or changes the original pruning semantics, whereas physical packing preserves the original KVzap decisions and retains nearly all compression.

Do not use B=4 as the main architecture assumption unless accuracy and system-level results unexpectedly make it superior.

---

## 19. RTL Scope

Do not build a complete LLM accelerator.

The recommended architecture-paper implementation target is a **dedicated KV-cache management and scheduling subsystem**.

### 19.1 Must implement in RTL

#### A. Streaming Admission / Packing Engine

Inputs conceptually include:

```text
keep
K
V
tail_page_state
```

Responsibilities:

- conditional keep/drop;
- tail-page write;
- page-boundary detection;
- new-page request;
- metadata update;
- backpressure handling.

#### B. Page Allocator / Metadata Manager

Responsibilities:

- free-page queue;
- head descriptor lookup/update;
- tail-page tracking;
- valid-count maintenance;
- new-page allocation;
- page-list management.

#### C. Final Scheduler

Implement the scheduling policy selected by simulation.

Responsibilities may include:

- task queue;
- PE availability tracking;
- dispatch;
- completion;
- fairness.

### 19.2 Conditional RTL

#### Partial Softmax Reducer

Implement only if page/chunk cross-PE parallelism provides clear performance benefit.

### 19.3 Not required in RTL

Model or reuse:

- KVzap predictor GEMM;
- Q/K/V projections;
- FFN;
- full Transformer;
- full HBM controller;
- complete attention MAC array.

These may be represented by parameterized throughput/bandwidth interfaces in the cycle model.

---

## 20. Final Evaluation Targets

The final research artifact should provide a complete chain of evidence.

### 20.1 Algorithm trace characterization

Show:

- high KVzap logical compression;
- poor suitability for large token blocks;
- low cross-head mask similarity;
- strong per-head workload imbalance.

### 20.2 Physical mapping

Show:

- packed per-head pages;
- near-original physical compression;
- low fragmentation;
- low metadata overhead.

### 20.3 Architecture simulation

Show:

- admission traffic;
- page allocation behavior;
- HBM traffic;
- static scheduling utilization;
- length-aware scheduling utilization;
- dynamic scheduling utilization;
- latency;
- throughput;
- break-even context/output length.

### 20.4 RTL

Report for new hardware modules:

- frequency;
- area;
- power;
- throughput;
- buffering requirements.

### 20.5 End-to-end projection

Combine:

- synthesized new modules;
- parameterized attention PE model;
- HBM model;

and report:

- memory footprint;
- HBM bandwidth reduction;
- decoding latency;
- tokens/s;
- energy;
- area overhead.

---

## 21. Recommended Codex Execution Order

Codex should proceed in the following order and should not jump directly to RTL.

### Phase 1 — Frozen algorithm and structural evidence

1. Preserve Phase-0 baseline, v2 predictor-only trace, and B=4 Route-B freeze.
2. Keep the original KVzap mask as the Route-A front-end contract.
3. Do not infer decode lifecycle or speed from the frozen prefill trace.

### Phase 2 — Build the static physical KV simulator

Implement:

```text
PackedKVSimulator
```

Support:

```text
page_size = 16, 32, 64, 128
```

First output final-state physical bytes, fragmentation, metadata, page count,
per-head capacity tails, and occupancy. This is a trace-derived static replay,
not a dynamic admission measurement.

### Phase 3 — Scheduler and traffic/cycle DSE

Before new model execution, simulate static-head, length-aware-head, and
page/chunk dynamic policies under declared page/PE/bandwidth/throughput
parameters. Construct batch `{1,2,4,8}` only by explicitly labelled offline
combination of independent traces.

### Phase 4 — Implement safe streaming admission replay

Replay real decoding traces.

Output:

- cold admissions per step;
- drop count;
- promotion bytes;
- page allocations;
- tail occupancy;
- cold-cache growth.

The collector must be read-only and establish trace-off/trace-on equivalence;
it must not reuse the failed stateful DMS/fake-key tracing path.

### Phase 5 — Calibrated attention and HBM cost models

Explicitly model:

- KV read bytes;
- attention compute;
- online softmax;
- metadata;
- scheduler overhead;
- admission;
- partial merge.

### Phase 6 — Architecture DSE

Sweep at least:

```text
page_size x PE_count x scheduler x batch_size
```

Select final architecture based on Pareto analysis.

### Phase 7 — Freeze the architecture specification

Before RTL, write:

```text
analysis/architecture_spec.md
```

It should define:

- page format;
- metadata format;
- buffers;
- queues;
- interfaces;
- scheduling policy;
- backpressure;
- timing assumptions;
- expected bandwidth;
- PE interface.

### Phase 8 — Implement RTL

Priority:

1. Admission/Packer
2. Allocator/Metadata
3. Scheduler
4. Partial Reducer only if justified

### Phase 9 — Final synthesis and system projection

Report area/power/frequency for new modules and integrate them into the end-to-end cycle model.

---

## 22. Stop / Go Criteria

Do not continue to RTL unless the simulator shows the following qualitatively:

### Storage

- physical compression remains close to logical KVzap compression;
- fragmentation and metadata are small.

### Admission

- one-time hot-to-cold packing cost is amortized within a reasonable future decode horizon.

### Scheduling

- measured workload imbalance causes meaningful utilization loss under a simple baseline;
- the proposed scheduler recovers a meaningful portion of that loss.

### System

- net HBM traffic reduction remains substantial after metadata and admission overhead;
- projected end-to-end decoding improvement is meaningful.

If any of these fail, revise the architecture before RTL.

---

## 23. Final Research Positioning

The architecture should ultimately be described as:

> A prediction-guided KV-cache execution substrate for KVzap-like pruning, where fine-grained, head-specific logical sparsity is preserved rather than forcibly blockified. Retained KV entries are streamed into per-head packed fixed-size pages, while a load-aware scheduler handles variable-length attention workloads. The design targets the gap between KVzap's logical compression and real memory/bandwidth/throughput gains.

The intended contribution is not simply "a sparse KV accelerator."

The intended contribution is:

\[
\text{Irregular logical KV pruning}
\rightarrow
\text{packed variable-length physical pages}
\rightarrow
\text{load-balanced attention execution}
\]

with explicit physical-memory, traffic, performance, and RTL validation.

---

## 24. Codex Working Rules

1. Do not silently change original KVzap pruning behavior.
2. Every architecture result must be trace-driven where possible.
3. Separate:
   - logical retained KV;
   - physical allocated KV;
   - actual bytes transferred;
   - modeled execution cycles.
4. Do not claim speedup from compression ratio alone.
5. Keep all new simulator assumptions explicit and configurable.
6. Add tests for every simulator component.
7. Record git commit, model, threshold, window size, trace ID, page size, scheduler mode, and batch construction for every result.
8. Before adding RTL complexity, verify that simulation shows the corresponding feature is necessary.
9. Prefer minimal architecture sufficient to recover most of the available benefit.
10. Maintain a clear distinction between:
    - measured model results;
    - trace-derived statistics;
    - cycle-model projections;
    - RTL synthesis results.
