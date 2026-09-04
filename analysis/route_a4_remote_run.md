# Route-A4 remote execution protocol

## Scope

Run `tools/run_kvzap_route_a40_integration_gate.py` first. It is a read-only
real-Qwen A4.0 integration gate, not A4.1 measurement: normal Full-KV remains
the model attention path; the runner independently checks a selected layer/KV
head's three-store Route-A reference against dense attention over the exact
same mask-selected records. Do not report its runtime as latency or throughput.

The gate must pass before implementing a policy-on transformer attention
replacement and before collecting A4.1 timing, allocator, or profiler data.

## Remote small gate

From the synced repository root on the server, first preserve its revision and
make sure the target directory does not already exist:

```bash
git status --short
uv lock --check
RUN_ID=route_a40_real_qwen_retrieval_small_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s tests/test_kvzap_route_a4_reference.py tests/test_kvzap_lifecycle.py tests/test_kvzap_admission_shadow.py tests/test_simulate_kvzap_packed_pages.py
.venv/bin/python tools/run_kvzap_route_a40_integration_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 0 \
  --output-dir "analysis/experiments/${RUN_ID}"
```

If the server's virtual environment uses a different Python executable,
substitute it consistently for both commands. Do not change model, predictor,
revision, threshold, window, page size, or admission budget in this first
gate. A context shorter than 129 tokens, a changed answer hash, no `q_len=1`
comparison, or any numerical mismatch is a failed gate—do not continue to
A4.1 measurement.

## Return artifact

Copy back exactly the newly created directory, including
`a40_real_qwen_integration_manifest.json`; do not overwrite an existing local
directory. For example, from the local checkout:

```bash
rsync -av remote-host:/remote/kvpress/analysis/experiments/route_a40_real_qwen_retrieval_small_01/ \
  /home/wz/AI/kvpress/analysis/experiments/route_a40_real_qwen_retrieval_small_01/
```

Also provide the server's `git status --short`, Python/Torch/Transformers
versions, GPU model, and the command's complete stdout/stderr. The manifest
already carries source hashes, answer digest, target layer/head, comparison
count, state summaries, and the maximum numerical difference needed for the
next review.

## Policy-on and non-empty-pending gate

After the preceding read-only integration manifest is accepted, synchronize
the policy backend files and run this separate fresh directory. The selected
layer-0/KV-head-0 GQA group now bypasses the original attention function on
every `q_len=1` decode call and reads only Route-A hot, pending, and packed K/V.
All other heads deliberately remain dense in this minimum generation gate.
The budget of one forces retained mature cold entries to remain in pending
staging, so `--require-pending-nonempty` is a required semantic guard, not a
performance setting.

```bash
RUN_ID=route_a40_policy_on_qwen_retrieval_pending_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4_reference.py \
  tests/test_kvzap_lifecycle.py \
  tests/test_kvzap_admission_shadow.py \
  tests/test_simulate_kvzap_packed_pages.py
.venv/bin/python tools/run_kvzap_route_a40_policy_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 0 \
  --admission-budget 1 \
  --require-pending-nonempty \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Return `a40_policy_on_qwen_manifest.json` from the new directory. A changed
Full-KV answer is permitted in this policy-on test; the required semantic guard
is per-call numerical equality between the substituted Route-A head and its
same-mask dense reference, plus explicit proof that pending staging was read.
Do not time this command or describe it as A4.1 measurement.

## Layer-complete policy-on gate

The next gate substitutes **every** KV-head GQA group in one selected layer.
It keeps other transformer layers dense, but eliminates the selected layer's
per-head dense fallback. The same intentionally small global admission budget
forces every selected head to exercise pending staging at least once.

```bash
RUN_ID=route_a40_policy_on_qwen_layer0_allheads_pending_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4_reference.py \
  tests/test_kvzap_lifecycle.py \
  tests/test_kvzap_admission_shadow.py \
  tests/test_simulate_kvzap_packed_pages.py
.venv/bin/python tools/run_kvzap_route_a40_policy_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head all \
  --admission-budget 1 \
  --require-pending-nonempty \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Return the complete fresh directory. Review requires a comparison row for each
selected KV head on every policy decode call, zero original-attention/fake-key
guards, and at least one nonzero pending count. `policy_coverage` records
per-head retained-cold and pending coverage: a selected head can validly have
no pending state when the original mask retained no mature cold token. This
still does not authorize A4.1 timing: it establishes only a layer-complete
semantic gate.

## Multi-layer policy-on gates

Schema `kvzap-route-a40-policy-on-qwen-gate-1.2` accepts a layer set. Start
with a separated early/middle/late probe; each listed layer has independent
Route-A state and its own per-head comparisons while sharing the frozen
predictor weights:

```bash
RUN_ID=route_a40_policy_on_qwen_layers_0_18_35_pending_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a40_policy_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers 0 18 35 \
  --target-kv-head all \
  --admission-budget 1 \
  --require-pending-nonempty \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Only after that manifest passes may the all-layer semantic gate run. It can be
substantially slower because this Python reference replaces every layer's
decode attention; it remains a semantic gate, not a timing experiment:

```bash
RUN_ID=route_a40_policy_on_qwen_all_layers_pending_02
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a40_policy_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers all \
  --target-kv-head all \
  --admission-budget 1 \
  --max-executed-dtype-ulps 16 \
  --require-pending-nonempty \
  --output-dir "analysis/experiments/${RUN_ID}"
```

For either manifest, every declared layer must have a positive
`policy_decode_call_count_by_layer`, and `policy_coverage.layers` must contain
every declared layer with one comparison row per selected KV head per decode
call. Do not run these commands with a timing wrapper or treat their elapsed
time as A4.1 evidence.

The FP32 same-mask `rtol`/`atol` comparison is the semantic guard. The
post-cast ULP control is a separately recorded execution-dtype diagnostic.
The default and command above use 16 ULP because an all-layer attempt observed
13 ULP after earlier policy-on low-precision layer outputs; it must be rerun
in a fresh directory with this declared limit. A FP32 mismatch still fails
regardless of this setting. Return the complete new directory and do not
overwrite the interrupted `_01` directory if it exists.

## Paired same-mask dense KVzap control

The accepted all-layer Route-A gate permits the next A4.0 control. The runner
now performs three untimed passes: Full-KV bypass, independent online
same-mask dense KVzap, and Route-A packed/pending/hot. The dense control keeps
the 128-token hot window and original predictor mask, but sends mature retained
cold K/V directly to dense lists. It has no pending FIFO, admission service, or
packed page. The run fails unless its per-layer mask digest and decision count
match Route-A exactly.

```bash
RUN_ID=route_a40_policy_on_qwen_all_layers_dense_baseline_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a4_reference.py \
  tests/test_kvzap_route_a_policy_backend.py
.venv/bin/python tools/run_kvzap_route_a40_policy_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers all \
  --target-kv-head all \
  --admission-budget 1 \
  --max-executed-dtype-ulps 16 \
  --with-same-mask-dense-baseline \
  --require-pending-nonempty \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Return the complete fresh directory. This establishes only the requested
functional baseline. Do not time the three passes or report it as A4.1.

If the online masks differ, the command intentionally exits nonzero after
writing `a40_online_mask_drift_diagnostic.json` in that fresh directory. Sync
that directory rather than rerunning with the same `RUN_ID`. The diagnostic
identifies bounded examples of the earliest layer/head/position keep/drop
differences and their two predictor scores; it contains no token text or K/V.

## Explicit replayed-mask paired baseline

The diagnostic establishes that independent online predictor passes are not a
strict same-mask pair for this request. The following separate control makes
Pass 2 the only online predictor source. Pass 3 replays Pass-2
`(layer, KV-head, position)` decisions exactly once and does not score its own
predictor. It therefore isolates the two attention/storage paths under exactly
the dense pass's original mask; it is not independent online Route-A evidence.

```bash
RUN_ID=route_a40_policy_on_qwen_all_layers_replayed_mask_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a4_reference.py \
  tests/test_kvzap_route_a_policy_backend.py
.venv/bin/python tools/run_kvzap_route_a40_policy_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers all \
  --target-kv-head all \
  --admission-budget 1 \
  --max-executed-dtype-ulps 16 \
  --with-same-mask-dense-baseline \
  --replay-dense-mask-for-route-a \
  --require-pending-nonempty \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Review requires `pairing_mode: "replayed_dense_mask"`, exact per-layer mask
digest equality, and `replay_mask_consumption_complete: true`. Do not compare
wall-clock time from these Python reference passes or use this result as an
online mask-stability claim.

## A4.1.0 no-model CUDA instrumentation self-check

Before loading Qwen for any A4.1 component measurement, synchronize the new
harness and run its CUDA tensor-add self-check in a fresh directory. It checks
CUDA event timing, host synchronization, raw-repetition writing, and PyTorch
allocator snapshots. It is not a KVzap performance run and must not be
compared with any A4.0/A4.1 model result.

```bash
RUN_ID=route_a41_harness_cuda_self_check_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s tests/test_kvzap_route_a41_measurement.py
.venv/bin/python tools/run_kvzap_route_a41_measurement_harness.py \
  --self-check \
  --device cuda \
  --warmup-repetitions 3 \
  --measured-repetitions 10 \
  --tensor-elements 1048576 \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Return the complete new directory. Review requires both harness manifests,
exactly 13 raw records for the command above (3 warm-up plus 10 reported),
synchronized finite wall/CUDA-event values, and byte-valued allocator fields.
This gate is successful instrumentation validation only; it does not authorize
a performance conclusion by itself.

## A4.1.1 one-layer/head replayed-mask component gate

The following is the first real-Qwen A4.1.1 measurement.  It has two commands
and two fresh directories.  The first command is intentionally **untimed**:
it creates the single online dense-KVzap source mask.  The second replays that
exact source through dense-cold and Route-A storage/attention states and
records component samples.  Do not use shell `time` around either command.

First run the local/remote unit tests and collect a layer-0 source.  The
source collector must finish before starting the component runner.

```bash
SOURCE_ID=route_a41_replay_source_layer0_budget1_01
test ! -e "analysis/experiments/${SOURCE_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a41_measurement.py \
  tests/test_kvzap_route_a4_reference.py \
  tests/test_kvzap_route_a_policy_backend.py
.venv/bin/python tools/collect_kvzap_route_a41_replay_source.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers 0 \
  --admission-budget 1 \
  --output-dir "analysis/experiments/${SOURCE_ID}"
```

Then run the paired component gate.  The `admission_budget=1` point is a
semantic-coverage measurement point: it is deliberately backlogged and must
show a Route-A pending component.  It must never be pooled with the later
candidate `admission_budget=512` point.

```bash
RUN_ID=route_a411_component_layer0_head0_budget1_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a41_component_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 0 \
  --admission-budget 1 \
  --require-pending-nonempty \
  --warmup-repetitions 3 \
  --measured-repetitions 10 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

## A4.1.1 schema-1.1 reset-run summary rerun

Synchronize the schema-1.1 update and use the already validated source. These
are fresh replacements for comparison only; do not modify prior artifacts.
The manifest must expose both `summary.callback_groups` and
`summary.reset_run_aggregate_groups`. Each observed component must have ten
reported reset runs. The latter's time is a component callback sum, and its
allocator peak is a run-local maximum; neither is end-to-end decode latency.

```bash
RUN_ID=route_a411_component_layer0_head0_budget1_summary11_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a41_component_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 0 \
  --admission-budget 1 \
  --require-pending-nonempty \
  --warmup-repetitions 3 \
  --measured-repetitions 10 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"

RUN_ID=route_a411_component_layer0_head0_budget512_summary11_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a41_component_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 0 \
  --admission-budget 512 \
  --warmup-repetitions 3 \
  --measured-repetitions 10 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

## A4.1.1 layer-0 KV-head-6 multi-page coverage

After the two head-0 schema-1.1 artifacts pass review, reuse the same source
for head 6. It contains up to 195 mature dense-cold tokens for that head. The
budget-one run proves pending coverage; the budget-512 run must prove actual
multi-page state, including one sealed full page. Neither command is an
end-to-end timing or allocator/HBM experiment.

```bash
RUN_ID=route_a411_component_layer0_head6_budget1_summary11_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a41_component_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 6 \
  --admission-budget 1 \
  --require-pending-nonempty \
  --warmup-repetitions 3 \
  --measured-repetitions 10 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"

RUN_ID=route_a411_component_layer0_head6_budget512_multipage_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a41_component_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 6 \
  --admission-budget 512 \
  --require-multi-page-packed \
  --warmup-repetitions 3 \
  --measured-repetitions 10 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

## A4.1.2 `{0,18,35}` whole-decode gate

Synchronize the A4.1.2 runner, then create a new replay source covering all
three selected layers. Source collection is untimed. The following runner
measures only question-forward plus greedy decode after an untimed context
prefill; it is not full-request latency and must not be wrapped in shell
`time`.

```bash
SOURCE_ID=route_a412_replay_source_layers_0_18_35_01
test ! -e "analysis/experiments/${SOURCE_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a41_measurement.py \
  tests/test_kvzap_route_a412_whole_decode.py \
  tests/test_kvzap_route_a4_reference.py \
  tests/test_kvzap_route_a_policy_backend.py
.venv/bin/python tools/collect_kvzap_route_a41_replay_source.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers 0 18 35 \
  --admission-budget 512 \
  --output-dir "analysis/experiments/${SOURCE_ID}"

RUN_ID=route_a412_whole_decode_layers_0_18_35_budget512_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a412_whole_decode_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers 0 18 35 \
  --target-kv-head all \
  --admission-budget 512 \
  --warmup-repetitions 3 \
  --measured-repetitions 10 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Return both new directories. Review requires the source's exact three-layer
coverage and SHA-256, 39 raw rows (3 paths x (3 warm-ups + 10 reported)), one
whole-decode record per path/reset run, ten reported reset runs for each path,
complete replay consumption in both replay paths, and explicit Full-KV bypass
with zero Route-A admission. Generated length and answer/token digests are
recorded rather than required to match Full-KV. A profiler, if needed, is a
separate later run.

## A4.1.2.1 separate profiler diagnostic

This is one attribution capture per paired path, not a timing benchmark. It
profiles only question-forward plus greedy decode after an untimed context
prefill. Do not wrap it in shell `time`, do not compare its wall duration with
A4.1.2 repetitions, and do not interpret its allocator or operator values as
HBM traffic, physical memory, throughput, or hardware results.

Reuse the reviewed A4.1.2 source exactly; only the profiler output directory
is new.

```bash
SOURCE_ID=route_a412_replay_source_layers_0_18_35_01
RUN_ID=route_a412_profiler_layers_0_18_35_budget512_gpu_summary11_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a412_whole_decode.py \
  tests/test_kvzap_route_a412_profiler.py \
  tests/test_kvzap_route_a4_reference.py \
  tests/test_kvzap_route_a_policy_backend.py
.venv/bin/python tools/run_kvzap_route_a412_profiler.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers 0 18 35 \
  --admission-budget 512 \
  --warmup-repetitions 1 \
  --top-operators 30 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Synchronize the whole fresh profiler directory, including
`a412_profiler_manifest.json`, `a412_profiler_operator_summary.json`, and all
three `a412_profiler_*.json` Chrome traces. Review checks the exact source
hash, one result for each path, answer/token-ID digests, complete replay for
both replay paths, and profiler scope/boundaries. The resulting operator table
only locates current Python-reference overhead before a separate true
cache-ownership/storage-substitution design.

The original schema-1.0 output directory must remain untouched. Schema 1.1
uses PyTorch's `device_time_*` aggregate fields (with legacy fallback), because
the PyTorch 2.10 build leaves its older `cuda_time_*` aggregate fields empty.
This is a profiler-summary field compatibility correction, not a K/V Cache
read, mask, or attention error. The raw Chrome traces are intentionally large;
for transfer, create lossless `.gz` copies after the run and keep the original
JSON or a documented decompression procedure.

## A4.1.2.2 selected-head native-cold ownership gates

These are untimed semantic integration gates. They poison mature selected-head
native-cache K/V after Route-A retains it, then ensure the selected Route-A
attention path remains finite and same-mask equivalent without consuming those
native dense cold values. Native DynamicCache slots remain allocated; do not
use these runs for latency, allocator, physical-memory, or HBM claims.

Reuse the completed layer-0 replay source. Run head 6 twice in fresh output
directories: budget one exercises pending staging, while budget 512 exercises
full-page/tail/multi-page packed state.

```bash
SOURCE_ID=route_a41_replay_source_layer0_budget1_01
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a4122_cache_ownership.py \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4_reference.py

RUN_ID=route_a4122_ownership_layer0_head6_budget1_pending_schema11_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a4122_cache_ownership_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 6 \
  --admission-budget 1 \
  --require-pending-nonempty \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"

RUN_ID=route_a4122_ownership_layer0_head6_budget512_multipage_schema11_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a4122_cache_ownership_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 6 \
  --admission-budget 512 \
  --require-multi-page-packed \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Synchronize both complete directories. Each schema-1.1 manifest must report
complete replay, the recorded same-mask dense/owned-cold generated-output
relation, nonzero native-cold poison writes/prior-read checks, and
`native_cold_slots_physically_freed: false`. Generated token drift does not
fail this gate by itself because the per-head FP32 numerical guard remains the
semantic criterion. The budget-one manifest must show pending coverage; the budget-512
manifest must show a sealed page plus multi-page coverage.

## A4.1.2.3 first-generation-logit prefix diagnostic

Run this before interpreting the token-0 drift from A4.1.2.2. It does not
generate tokens, measure time, or consume the full replay source. It captures
whether the first-generation logits are finite and whether the multi-token
question forward actually reached q_len=1 Route-A policy attention.

```bash
SOURCE_ID=route_a41_replay_source_layer0_budget1_01
RUN_ID=route_a4123_first_logits_layer0_head6_budget1_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a4123_first_decode_logits.py \
  tests/test_kvzap_route_a4122_cache_ownership.py \
  tests/test_kvzap_route_a_policy_backend.py
.venv/bin/python tools/run_kvzap_route_a4123_first_decode_logits_diagnostic.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 6 \
  --admission-budget 1 \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Synchronize the fresh directory. Review `question_token_count`,
`policy_decode_calls`, prefix replay consumption, finite/NaN/Inf fields, and
the dense-vs-Route-A logit relation. A nonfinite Route-A result with no policy
decode calls is a native fallback/ownership-scope failure, not a performance or
softmax-tolerance conclusion.

## A4.1.2.4 causal multi-token bridge gate

```bash
SOURCE_ID=route_a41_replay_source_layer0_budget1_01
# Schema 1.1: both Route-A and the same-mask dense control bridge q_len>1.
RUN_ID=route_a4124_multitoken_bridge_layer0_head6_budget1_densebridge_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s tests/test_kvzap_route_a_policy_backend.py tests/test_kvzap_route_a4123_first_decode_logits.py
.venv/bin/python tools/run_kvzap_route_a4124_multitoken_bridge_gate.py \
  --preset retrieval --context-repetitions 12 --max-new-tokens 8 \
  --target-layer 0 --target-kv-head 6 --admission-budget 1 --top-k 8 --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Synchronize the fresh directory. It must show bridge coverage for both the
same-mask dense control and Route-A, their bounded per-token attention-summary
diagnostics, finite paired logits, equal first argmax, prefix replay accounting,
and no physical-slot-freeing claim. The old `layoutfix_01` artifact establishes
the output-layout repair only; its dense q_len>1 path was native Full-KV and is
not a valid numerical same-mask baseline.

## A4.1.2.5 full-page/tail/multi-page semantic gate

This is a new output directory and reuses the already frozen replay source;
changing admission budget must not change the source mask. Do not require
pending staging here: the budget-one gate already covered it and high admission
can drain it before the question bridge.

```bash
SOURCE_ID=route_a41_replay_source_layer0_budget1_01
RUN_ID=route_a4125_multitoken_bridge_layer0_head6_budget512_multipage_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a4124_multitoken_bridge_gate.py \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4123_first_decode_logits.py
.venv/bin/python tools/run_kvzap_route_a4124_multitoken_bridge_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 6 \
  --admission-budget 512 \
  --require-multi-page-packed \
  --require-full-packed-page \
  --require-tail-packed-page \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Synchronize the fresh directory. Review the schema-1.2 observed page guards,
packed-page/full-page/tail counts, causal bridge coverage, ownership guards,
and same-mask dense versus Route-A diagnostics. This run is not a performance,
allocator, HBM, or physical-memory measurement.

## A4.1.2.6 simultaneous all-KV-head ownership gates

The runner now accepts `--target-kv-head all`. Every layer-0 KV head must have
one bridge comparison for each question token; aggregate state flags require a
state on at least one head, not every low-retention head. Run the pending gate
first, then synchronize and review it before the multipage gate.

```bash
SOURCE_ID=route_a41_replay_source_layer0_budget1_01
RUN_ID=route_a4126_allheads_layer0_budget1_pending_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a4124_multitoken_bridge_gate.py \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4123_first_decode_logits.py
.venv/bin/python tools/run_kvzap_route_a4124_multitoken_bridge_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head all \
  --admission-budget 1 \
  --require-any-pending \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

After the pending artifact is reviewed, use a different fresh directory for
the all-head page-boundary gate:

```bash
RUN_ID=route_a4126_allheads_layer0_budget512_multipage_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a4124_multitoken_bridge_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head all \
  --admission-budget 512 \
  --require-any-multi-page-packed \
  --require-any-full-packed-page \
  --require-any-tail-packed-page \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Each manifest must resolve all eight KV heads, record 22 comparisons per head
for both dense and Route-A bridges, preserve native cold ownership guards, and
pass its explicit aggregate state guard. These are semantic prefix gates only;
they are not all-layer, full-decode, timing, allocator, HBM, or hardware
measurements.

## A4.1.2.7 all-head downstream-activation diagnostic

This tool registers temporary layer hooks and is therefore intentionally
untimed. It saves scalar summaries only, never activation tensors. Run the
pending configuration first; synchronize and inspect it before the page-boundary
configuration.

```bash
SOURCE_ID=route_a41_replay_source_layer0_budget1_01
RUN_ID=route_a4127_allheads_layer0_budget1_pending_activation_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a_activation_diagnostic.py \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4124_multitoken_bridge_gate.py \
  tests/test_kvzap_route_a4123_first_decode_logits.py
.venv/bin/python tools/run_kvzap_route_a4127_allhead_activation_diagnostic.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head all \
  --admission-budget 1 \
  --require-any-pending \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

After reviewing the budget-one artifact, use a fresh ID for the page-boundary
configuration:

```bash
RUN_ID=route_a4127_allheads_layer0_budget512_multipage_activation_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a4127_allhead_activation_diagnostic.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head all \
  --admission-budget 512 \
  --require-any-multi-page-packed \
  --require-any-full-packed-page \
  --require-any-tail-packed-page \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

The manifest must have a 36-layer scalar relation table, no serialized
activation tensors, explicit guard request/satisfaction metadata, all eight
heads with 22 comparisons each, and the requested aggregate state. It is not a
timing, memory, HBM, quality, full-decode, or hardware experiment.

## A4.1.2.8 bounded all-head continuation consequence diagnostic

This is intentionally **untimed**. It distinguishes a paired, same-generated-
input logit check (Route-A forced to use the dense token IDs) from an
independent Route-A greedy trajectory. Do not treat a later independent row
after a mismatch as a same-input numerical comparison. Run the pending case
first and synchronize the complete fresh directory for review.

```bash
SOURCE_ID=route_a41_replay_source_layer0_budget1_01
RUN_ID=route_a4128_allheads_layer0_budget1_pending_continuation_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a_continuation_diagnostic.py \
  tests/test_kvzap_route_a_activation_diagnostic.py \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4124_multitoken_bridge_gate.py \
  tests/test_kvzap_route_a4123_first_decode_logits.py
.venv/bin/python tools/run_kvzap_route_a4128_allhead_continuation_diagnostic.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head all \
  --admission-budget 1 \
  --require-any-pending \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

After reviewing that manifest, run the separate packed-page state companion:

```bash
RUN_ID=route_a4128_allheads_layer0_budget512_multipage_continuation_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a4128_allhead_continuation_diagnostic.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head all \
  --admission-budget 512 \
  --require-any-multi-page-packed \
  --require-any-full-packed-page \
  --require-any-tail-packed-page \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Return each complete fresh directory. The manifest must show replay completion,
all eight heads' multi-token bridge coverage, native-cold ownership coverage,
the forced paired per-step relations, and the independent token-ID relation.
It is not timing, quality, Full-KV, allocator/HBM, or hardware evidence.

## A4.1.2.9 `{0,18,35}` all-head multi-layer continuation diagnostic

This next gate needs a **new** replay source because original KVzap mask events
are layer-addressed. It is untimed. First collect the source; its online dense
KVzap run records mask events only and is not a performance measurement.

```bash
SOURCE_ID=route_a4129_replay_source_layers_0_18_35_01
test ! -e "analysis/experiments/${SOURCE_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4129_multilayer_continuation.py \
  tests/test_kvzap_route_a_continuation_diagnostic.py
.venv/bin/python tools/collect_kvzap_route_a41_replay_source.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers 0 18 35 \
  --admission-budget 1 \
  --output-dir "analysis/experiments/${SOURCE_ID}"
```

Synchronize and review the completed source manifest before running the pending
continuation gate. Then use a different new output directory:

```bash
RUN_ID=route_a4129_layers_0_18_35_budget1_pending_continuation_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a4129_multilayer_continuation_diagnostic.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers 0 18 35 \
  --target-kv-head all \
  --admission-budget 1 \
  --require-any-pending \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

The output must show each of layers 0, 18, and 35 with all KV heads bridged,
complete replay consumption, independent ownership poisoning/read guards, and
the forced/independent token relations. It is not an all-36, timing, quality,
allocator/HBM, or hardware experiment. Review this pending artifact before the
separate budget-512 page-state counterpart.

After the budget-one manifest has passed review, reuse its immutable source in
a fresh multi-page page-state gate:

```bash
SOURCE_ID=route_a4129_replay_source_layers_0_18_35_01
RUN_ID=route_a4129_layers_0_18_35_budget512_multipage_continuation_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a4129_multilayer_continuation_diagnostic.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers 0 18 35 \
  --target-kv-head all \
  --admission-budget 512 \
  --require-any-multi-page-packed \
  --require-any-full-packed-page \
  --require-any-tail-packed-page \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

The review must separately confirm all three layers' replay and ownership
guards, page-state coverage, and forced/independent greedy relations. It stays
an untimed semantic gate.

## Next A4.1.2.10 scope — all 36 layers, all KV heads

The `{0,18,35}` pending and page-state gates are complete. The next semantic
scope is all 36 layers simultaneously, but it begins with a fresh all-layer
replay source and a budget-one pending gate. Do not substitute an all-36 timing
runner or reuse the three-layer source.

```bash
SOURCE_ID=route_a4130_replay_source_all_layers_01
test ! -e "analysis/experiments/${SOURCE_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4129_multilayer_continuation.py \
  tests/test_kvzap_route_a_continuation_diagnostic.py
.venv/bin/python tools/collect_kvzap_route_a41_replay_source.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers all \
  --admission-budget 1 \
  --output-dir "analysis/experiments/${SOURCE_ID}"
```

Synchronize and review the complete source before the all-layer pending gate.
The source must resolve exactly all 36 layers; for this request/horizon, expect
268,992 events if each layer reproduces the 7,472-event stream.

```bash
RUN_ID=route_a4130_all_layers_budget1_pending_continuation_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a4130_alllayer_continuation_diagnostic.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers all \
  --target-kv-head all \
  --admission-budget 1 \
  --require-any-pending \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

The required contract is independent per-layer replay and ownership guards,
all-head bridge coverage, forced common-token diagnostics, and independent
greedy diagnostics. Review this artifact before its separately fresh budget-512
page-state companion; it remains untimed.

If the runner reports an execution-dtype ULP failure, do not reuse its output
directory or increase `--max-executed-dtype-ulps`. Synchronize the fresh
directory containing `a4130_alllayer_continuation_numerical_guard_failure.json`.
After updating to the failure-diagnostic code, rerun the identical command with
a new `RUN_ID` ending in `_02`; the scalar record is the required input for the
next numerical-policy decision.

## A4.1.2.11 — record-only all-layer ULP distribution (not acceptance)

The A4130 `_02` failure identified a near-zero BF16 ULP amplification while
the hard FP32 same-mask guard passed. Do not increase the ULP limit and do not
run budget 512. First collect the bounded scalar distribution below, using the
already synchronized immutable all-layer source. This entrypoint retains FP32
same-mask/replay/bridge/ownership guards; it changes only the post-cast ULP
response to scalar recording.

```bash
SOURCE_ID=route_a4130_replay_source_all_layers_01
RUN_ID=route_a4131_all_layers_budget1_ulp_distribution_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python -m pytest -q -s \
  tests/test_kvzap_route_a_policy_backend.py \
  tests/test_kvzap_route_a4129_multilayer_continuation.py
.venv/bin/python tools/run_kvzap_route_a4131_alllayer_ulp_distribution_diagnostic.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layers all \
  --target-kv-head all \
  --admission-budget 1 \
  --max-executed-dtype-ulps 16 \
  --ulp-breach-sample-limit 8 \
  --require-any-pending \
  --top-k 8 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```

Synchronize only the fresh A4131 directory. Review its three per-path
`execution_dtype_ulp_breaches` summaries alongside replay/bridge/ownership
guards. The samples are bounded scalar metadata, not tensors. A completed
manifest reports a distribution only; it does not establish an accepted
all-layer numerical tolerance or permit budget-512 or timing work.

Return both complete fresh directories.  Review requires a completed source
manifest with a matching NPZ SHA-256, an A4.1.1 manifest with complete replay
consumption, raw JSONL, three warm-ups and ten reported repetitions for every
observed component/path, plus at least one Route-A row with nonzero pending
tokens.  The raw callback timings are synchronized micro-component samples;
they do not measure Full-KV, end-to-end decode, HBM traffic, throughput,
energy, area, or hardware acceleration.  Do not add
`--include-online-predictor-control` to this first paired gate; it is an
optional, separately labelled predictor-score control for a later diagnostic.

After the budget-one artifact is reviewed, run the candidate admission point
in another new directory. Reuse the same replay source: admission does not
participate in source-mask generation. Do **not** pass
`--require-pending-nonempty`; an empty pending FIFO is valid at this point.

```bash
RUN_ID=route_a411_component_layer0_head0_budget512_01
test ! -e "analysis/experiments/${RUN_ID}"
.venv/bin/python tools/run_kvzap_route_a41_component_gate.py \
  --preset retrieval \
  --context-repetitions 12 \
  --max-new-tokens 8 \
  --target-layer 0 \
  --target-kv-head 0 \
  --admission-budget 512 \
  --warmup-repetitions 3 \
  --measured-repetitions 10 \
  --device cuda \
  --replay-source-dir "analysis/experiments/${SOURCE_ID}" \
  --output-dir "analysis/experiments/${RUN_ID}"
```
