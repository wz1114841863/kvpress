# A4.14.0 — workload-aligned metadata-cost binding contract

## Purpose

A4.14.0 supplies the one missing alignment required before A4.14 can form an
accounted Route-A ledger.  A4.12.2's 168 metadata contexts and the three
A4.11.2b Qwen external-storage workloads are not numerically paired.  This
stage reconstructs the already-frozen deterministic token-to-span transaction
groups from each accepted A4.11.2b lifecycle trace and replays **only** the
already-selected complete metadata proxy mapping:

```text
prefill-armed external-storage lifecycle
  -> frozen replay-mask retained token
  -> 64-token span / append-event / layer / KV-head group
  -> fixed HA8-wide record-granular lossless replay
  -> M2 metadata macro-access and declared service accounting
```

It is a binding replay, not a new metadata DSE.  It does not run a model or
create a new lifecycle trace.

## Frozen inputs and choices

- A4.11.2b binding `_02`, including its exact lifecycle manifests, compressed
  lifecycle traces, replay-mask hashes, Qwen3-8B setup and token guards.
- A4.12.0 `_02`, A4.12.1 `_03`, A4.12.2 `_02`, and A4.10 `_04`.
- HA8-wide, head-affine eight-bank, record-granular execution;
  local32/shared256/staging512; the existing per-head FIFO, lossless credit,
  ownership, dependency and one external commit boundary.
- M2 (`replicated_or_duplicated_control_storage`) only.  M1 remains rejected
  and M3 remains incomplete because its register cost is deliberately absent;
  neither is rerun or selected here.

The M2 public-CACTI area is a single **fixed provisioned metadata-engine proxy
cost**.  It is reported once in the result and never summed once per workload.
Each workload has separate trace-bound transaction counts and workload-
dependent M2 macro access/estimated dynamic-energy observations.

## Output and evidence classes

For retrieval, summarization and reasoning, report exact source hashes,
transaction-group reconstruction, drain/residual, declared local/shared/
staging/held high-watermarks, M2 macro accesses, estimated M2 SRAM dynamic
energy and metadata service-coordinate summaries.

| Item | Evidence class |
|---|---|
| lifecycle maturity and final state guards | direct software observation |
| retained-token to span/group lowering | deterministic conversion |
| bank mapping, queue state, M2 service cycle and drain | declared model |
| M2 macro pJ/access and fixed area | public CACTI proxy |

The declared metadata service coordinate is deliberately separate from
A4.13.5 payload-service coordinates.  A4.14.0 must not add them, claim a
physical FIFO depth, measured throughput/energy, end-to-end latency,
architecture readiness, or RTL.

## Exit gate

The report is accepted only if all three workloads retain the exact upstream
token/lifecycle guards, reconstruct exactly the A4.11.2b group count, preserve
the fixed commit/queue semantics, and drain losslessly under M2.  Failure is a
binding result for A4.14; it must not retune queue, scheduler, pruning,
admission, execution granularity, or metadata organization.
