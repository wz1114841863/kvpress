# RD2 local validation r4 interruption — 2026-11-06

## Disposition

The local run from source revision `16542a5` did not complete successfully.
`/tmp/kvzap_rd2_local_20261106_r4.log` ends with
`KVZAP_RD2_LOCAL_TEST_EMIT_EXIT=143`; the pane also records `Terminated`.
There is no complete two-test PASS, paired-emitter PASS or generated output
root `/tmp/kvzap_rd2_read_inputs_20261106_r4`.

No RD2 validation/compiler process remains.  The tmux shell
`kvzap-rd2-local:rd2-test` remains available.  No remote RD2 DC was launched.

## Evidence and failure layer

Java 21/Scala source compilation completed.  The 4 x 8 test constructed its
simulator and its execution transcript reaches the final `D` command.  The
suite then reached the 36 x 64 simulator build.  The full-size simulator binary
and execution transcript were never produced; there is no full-size RTL
assertion failure or functional result to evaluate.

The kernel records a new global OOM event during this build:

- killed process: `cc1plus`, PID 12341;
- anonymous RSS: 11,672,100 KiB, approximately 11.1 GiB;
- total virtual memory: 23,219,060 KiB;
- task belongs to the local tmux scope used by this run.

The OOM event is distinct from the earlier r2 compiler kill.  Exit 143
indicates the outer process received SIGTERM; that exit code alone does not
identify OOM.  The kernel event and incomplete C++ compilation independently
establish compiler-memory failure during the full-size build.

## Why the earlier split settings were insufficient

The actual Verilator invocation includes `-j 2`, `--output-split 2000` and
`--output-split-cfuncs 200`.  The installed tool identifies itself as
Verilator 5.041 devel, revision `v5.040-350-g6ec5c85be`.

Its generated `VsvsimTestbench_classes.mk` compiles only two fast grouped
translation units, `VsvsimTestbench_vm_classes_0` and `_1`, plus two slow
groups.  `VsvsimTestbench_vm_classes_0.cpp` includes the already split
`VsvsimTestbench___024root__0.cpp` through `__6.cpp` in one C++ translation
unit.  The compiler log confirms the grouped units are compiled with `-Os`.

Consequently, splitting output files and limiting job count did not bound the
size or optimizer memory of each translation unit.  The previous assumption
that those settings alone controlled build memory is disproved by this run.

The next repair should explicitly control Verilator output grouping, confirm
from generated makefiles and actual compiler commands that split files stay
separate, and bound compiler parallelism/optimization.  Inspect the installed
tool's `--output-groups` behavior before choosing a value.  This is simulator
build configuration; preserve the final 144-bit C read, helper RTL, test
stimulus, full geometry and synthesis comparison.

## Next gate

This inspection changes documentation only and does not restart the run.
Preserve r4 and its native build diagnostics.  Require full functional and
emitter closure in a new successor before preparing RD2 small synthesis.  No
area, timing, production-integration or hardware-benefit result exists for RD2.
