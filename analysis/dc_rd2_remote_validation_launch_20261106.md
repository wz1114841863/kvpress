# RD2 remote functional/emission launch — 2026-11-06

## Active run

- tmux: `kvzap-control-refine:p26-rd2-test-emit-r2`;
- source revision: `48f8cf3ba7ffcbdd3151a7616f096b5876da633b`;
- runner repair revision: `342f024`;
- output root:
  `/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/rd2_remote_validation_48f8cf3_p26_r2`;
- outer log:
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/rd2_remote_p26_r2_test_emit_20261106.log`;
- runner terminal marker: `KVZAP_RD2_REMOTE_VALIDATION_EXIT=<code>`;
- wrapper terminal marker: `KVZAP_RD2_P26_R2_REMOTE_OUTER_EXIT=<code>`.

The source archive is
`/home/yaz80/wz_project/chisel_projects/kvpress/bundles/rd2_source_48f8cf3_20261106_r1.tar`,
SHA-256 `582c87b96a4ae68e687e94f059cf5fd95404bd76739e5768733eb51b3ee6a8d0`.
The runner SHA-256 is
`747df4d199dd12f635d7bab3af479083b7534dd8db4a02a26e53c893aaa91410`.
Both identities were independently checked after remote transfer.

The archive extracts into a new workspace under the output root.  It does not
reuse the shared Chisel source/build tree or any active/frozen DC input.

## Launch evidence

The repaired runner executes the proven native OpenJDK 11.0.19 runtime,
with Java heap capped at 4 GiB and two JVM active processors.  Native Java
startup succeeds, unlike the preserved p25 glibc failure.  About 42 GiB of
memory is available at preflight.

At launch:

- `KVZAP_RD2_REMOTE_PREFLIGHT_PASS` is present;
- `KVZAP_RD2_REMOTE_INPUT_PASS` is present;
- `KVZAP_RD2_REMOTE_STACK_PASS stack_kb=unlimited` is present;
- sbt 1.11.5 has loaded the isolated project under the new root;
- the Java process is live, with no native startup error;
- the independent RD1 PID 25891 remains live and unchanged.

The final source retains the complete 4 x 8 and 36 x 64 tests, the 144-bit C
payload/suffix output and independent readers.  Only simulator build
concurrency differs from local r4: one C++ build job and two Verilation jobs.

## Completion gate

Wait for user-reported completion.  Require both outer exits zero, the two
test cases with zero failures/errors/skips, `All tests passed.`, the paired
emitter marker and `KVZAP_RD2_REMOTE_POSTCHECK_PASS`.  Independently verify
the input/source hashes, paired port-header identity and output hashes in
`output_manifest.json`.

No DC invocation is part of this job.  A functional/emission pass supplies
inputs for the separately checked RD2 small-synthesis screen.  It does not
establish RD2 area/timing or authorize production integration.
