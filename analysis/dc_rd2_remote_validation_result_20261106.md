# RD2 remote functional and RTL-emission result — 2026-11-06

## Disposition

The corrected run in `kvzap-control-refine:p26-rd2-test-emit-r2` completes
successfully.  Native Java 11 resolves the preserved p25 Java-21/glibc startup
failure, and the EDA server completes the full-size simulator build that
exceeded local resources.

Acceptance markers are all present:

- two tests succeeded, zero failed/canceled/ignored/pending;
- `All tests passed.`;
- `RD2_SCREEN_INPUT_EMIT_PASS`;
- `KVZAP_RD2_REMOTE_POSTCHECK_PASS tests=2 paired_ports_identical=true`;
- `KVZAP_RD2_REMOTE_VALIDATION_EXIT=0`;
- `KVZAP_RD2_P26_R2_REMOTE_OUTER_EXIT=0`.

The suite reports 44 minutes 9 seconds, with sbt total 2,692 seconds including
source compilation.  Paired emission takes eight seconds.  The shell remains
in tmux; no RD2 JVM/compiler process remains.

## Independent provenance and output closure

The source archive hash independently rechecks to
`582c87b96a4ae68e687e94f059cf5fd95404bd76739e5768733eb51b3ee6a8d0`.
All 133 source files recorded by the input manifest rehash exactly.
The test XML independently reports two cases, zero failures/errors/skips:

1. independent raw reads and pre-edge writes at 4 x 8;
2. independent raw reads and pre-edge writes at 36 x 64.

Both emitted module port headers are independently compared after whitespace
normalization and are identical.  The files are:

| input | size | SHA-256 |
|---|---:|---|
| `rd2_rd1_read_network.sv` | 945,317 bytes | `f8080b6d97ab82d2aeed309774cc64e2481b0552a34c78d3c7d1079d6346fb1f` |
| `rd2_decoded_read_network.sv` | 1,463,197 bytes | `caf0f8cf9c3b05e05e748386d560a4574fe715359ef2546ba368c06a4261280c` |

Input manifest SHA-256 is
`f998db769d660701d173279aff97e6134a209d714de14c180f933b4a0e6a567a`.
Output manifest SHA-256 is
`3a0ed8f28c71ae170267042290e0ad08806f53f64f660c918621af755dec42b4`.
All outputs are under
`/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/rd2_remote_validation_48f8cf3_p26_r2`;
the accepted outer log remains
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/rd2_remote_p26_r2_test_emit_20261106.log`.

## Interpretation and next gate

RD2 now has bounded functional and paired-input closure for the isolated
decoded-reader experiment.  It preserves the RD1 reader on both sides and
tests the four remaining raw reads, including valid-low and concurrent reads,
against the same register images and scoreboard.  Its equivalence boundary
is still in-range layer/ordinal; production out-of-range/ready behavior remains
an explicit later integration gate.

The larger generated candidate SV is not mapped-area evidence.  No RD2 small
synthesis or complete DC has run, so there is no RD2 area/timing benefit to
accept or reject yet.  The next concrete step is to freeze this paired input
in an isolated fair-v1 read-network screen and measure its incremental result
against the RD1-enabled side.  This inspection does not launch that screen.

PM1's saved-DDC validation p24 remains complete with native/postcheck PASS and
both exits zero; p23's stale-summary errors remain preserved in its historical
log.  RD1's complete result is separately recorded in
`dc_rd1_full_paired_dc_result_20261106.md`.  No KVZap DC/test process remains
active at this inspection snapshot.  This result establishes no PPA, system
acceleration or hardware net benefit.
