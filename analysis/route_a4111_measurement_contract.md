# A4.11.1 trace-off three-path software measurement

## Scope

A4.11.1 is entered only after a completed A4.11.0 trace-off semantic matrix.
For each retrieval, summarization, and reasoning preset it consumes a fresh
online dense replay-mask source and runs the established all-layer/all-KV-head
external-storage measurement with three paths: Full-KV bypass, replayed
same-mask dense KVzap, and replayed same-mask Route-A external storage.

The new matrix validator requires the A4.11.0 configuration unchanged, a
completed measurement for every workload, one timed region per reset run,
replay consumption, all-layer external-storage ownership, and equal generated
token digests for the paired dense and Route-A paths.  It reports the median
wall/CUDA-event time and PyTorch allocator peaks as software observations.

## Boundary

The measurement neither changes nor calibrates A4.10's local `32`, shared
`256/layer`, staging `512/layer`, or HA8-wide contract.  It does not claim
HBM traffic, FIFO depth, credit latency, hardware throughput, energy, area, or
RTL behavior.  A later trace-on control-event stage is required to compare
software lifecycle behavior with A4.10's queue/control envelope.

## Run order

1. Create three fresh A4.11.0 trace-off policy manifests and validate their
   matrix.
2. For each workload, collect a fresh all-layer/all-KV-head replay source with
   `collect_kvzap_route_a41_replay_source.py` and admission budget `512`.
3. For each source, run
   `run_kvzap_route_a4147_qwen_external_storage_whole_decode_measurement.py`
   in a fresh output directory using the same workload/configuration.
4. Validate the three measurement manifests with:

```bash
.venv/bin/python tools/validate_kvzap_route_a4111_measurement_matrix.py \
  --a4110-report analysis/experiments/<a4110-matrix>/a4110_trace_off_semantic_matrix_report.json \
  --retrieval-measurement analysis/experiments/<retrieval-measurement>/a4147_external_storage_whole_decode_manifest.json \
  --summarization-measurement analysis/experiments/<summarization-measurement>/a4147_external_storage_whole_decode_manifest.json \
  --reasoning-measurement analysis/experiments/<reasoning-measurement>/a4147_external_storage_whole_decode_manifest.json \
  --preflight-only \
  --output-dir analysis/experiments/<new-a4111-matrix>
```
