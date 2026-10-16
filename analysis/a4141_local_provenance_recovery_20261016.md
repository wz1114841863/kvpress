# A4.14.1 local provenance recovery — 2026-10-16

## Purpose and boundary

This is a narrowly scoped repair record for the SRP.5 availability blocker:
the accepted, ignored A4.14.1 materialized ledger and the inputs needed by its
original preflight were absent from this local checkout. It records a
read-only recovery from the `algorithm` host's historical `zsy` worktree and a
local preflight. It creates no new A4 output, reruns no DSE, and changes no
Route-A behavior, contract, partition, or cost quantity.

The recovered files remain ignored experiment artifacts; they are deliberately
not added to Git. Their local availability permits inspection and revalidation
of the accepted proxy-ledger constraints only. It does not establish a memory
macro, HBM controller, numeric implementation, timing, throughput, energy,
area, PPA, or final net-benefit result.

## Source and transfer discipline

The source was the existing file set under
`algorithm:/home/myserver/workplace1/zsy/zsy_2/kvpress`. The `zsy` tmux
session identified that historical working directory; no tmux command was used
to start, resume, or alter an experiment. Before every transfer the local
target was checked absent, the remote object was checked as a regular file,
and its SHA-256 was read. Each file was then copied with `scp -p` to its
original materialized path and SHA-256 checked again locally.

## Recovered closure

| Role | Local materialized path | SHA-256 |
|---|---|---|
| Accepted A4.14.1 ledger | `analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/a4141_accounted_net_benefit_ledger_report.json` | `0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb` |
| Direct A4.13.1 input | `analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4131_source.json` | `ba6ec8291d213317e953dd0ac3a050524cf10a327705c6390fe652531a98950c` |
| Direct A4.13.3 input | `analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4133_source.json` | `fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1` |
| Direct A4.13.5 input | `analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4135_source.json` | `8a3c07255d8e6382807701b437935c89207b60065df5d671dacad0b8cfb7a502` |
| Direct A4.14.0 input | `analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4140_source.json` | `3d3cc52eade09c20ed305159d78b7bc43673db0072a4d1b9bc211bd061ae8034` |
| A4.14.0 transitive A4.11.2b input | `analysis/experiments/route_a4140_workload_aligned_metadata_cost_01/input_artifacts/a4112b_source.json` | `57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3` |
| A4.11.2b retrieval lifecycle | `analysis/experiments/route_a4140_workload_aligned_metadata_cost_01/input_artifacts/lifecycle/retrieval/a4112b_external_storage_lifecycle.jsonl.gz` | `0b5ca92920b4a9a243cc3631bbb37005d558bf8330251eb9e5080746bed87f30` |
| A4.11.2b summarization lifecycle | `analysis/experiments/route_a4140_workload_aligned_metadata_cost_01/input_artifacts/lifecycle/summarization/a4112b_external_storage_lifecycle.jsonl.gz` | `60aa2000582d350400de1dd3e8f77abb07196b5690522aa6e9fb5c16860d7cdf` |
| A4.11.2b reasoning lifecycle | `analysis/experiments/route_a4140_workload_aligned_metadata_cost_01/input_artifacts/lifecycle/reasoning/a4112b_external_storage_lifecycle.jsonl.gz` | `3776cd5c0a2170fc5e7f4952a178c624e479777da710491b1a7e0405f263b74f` |

The recovered report has schema
`kvzap-route-a4141-accounted-net-benefit-ledger-1.0`, status `complete`, and
its recorded source commit is `807c521c915532c9ca550d9baeb9094c800ddee6`.
These are provenance fields of the accepted historical report, not the current
RTL/SRP commit or a new analysis result.

## Local preflight

The exact existing analyzer was run only in preflight mode:

```text
.venv/bin/python tools/analyze_kvzap_route_a4141_accounted_net_benefit_ledger.py \
  --a4131-report analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4131_source.json \
  --a4133-report analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4133_source.json \
  --a4135-report analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4135_source.json \
  --a4140-report analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/input_artifacts/a4140_source.json \
  --output-dir /tmp/kvzap-a4141-srp-local-preflight-unused --preflight-only
```

It passed with: `exact bindings, common/incremental cost separation,
no-cycle-addition rule, HBM gate=True, positive-budget=True; no output
created.` The boolean checks reconfirm the accepted report's conditional
proxy-ledger predicates from its exact inputs. They do not measure hardware,
replace the listed unestimated terms, or authorize a new A4 result.

For reference only, the recovered report retains its accepted differential
omitted-dynamic-cost constraints of 27.646, 40.498, and 167.442 mJ/request for
retrieval, summarization, and reasoning respectively (unrounded values remain
inside the report). They constrain the difference between unestimated Route-A
and Full-KV dynamic terms; they are not a cost allowance and are not physical
energy validation.

## Disposition

**Resolved:** the specific SRP.5 blocker that prevented local, read-only
A4.14.1 ledger and budget revalidation.

**Still unresolved:** future synthesis-top membership and integration cost;
all selected memory/numeric/controller realization choices; missing
owner-carried action evidence; every explicitly unestimated term; and any
physical or end-to-end net-benefit conclusion. SRP.5's conditional pass and
its separately authorized realization-choice planning gate are unchanged.
