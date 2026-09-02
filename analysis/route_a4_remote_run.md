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
