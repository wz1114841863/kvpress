# RD2 validation migration to EDA server — 2026-11-06

The local r4 full-size simulator compilation exceeded local memory.  Move
the unchanged 4 x 8 / 36 x 64 differential tests and paired RTL emission to
an isolated EDA-server source snapshot.  Local Scala compilation succeeded;
no additional local full-size simulator build is needed before this move.

The simulator settings now request one C++ build job and two Verilation jobs
using the existing Chisel backend's separate controls.  This caps concurrent
compiler memory while preserving output/function split settings, full test
geometry, helper RTL, stimulus and eventual synthesis comparison.

`run_rd2_remote_validation.sh` accepts a new root and a SHA-256-pinned source
tar.  It requires at least 30 GiB available memory, extracts an independent
workspace, records all source hashes, and uses the installed Java 21,
Verilator and firtool 1.158.0 platform.  Java heap is capped at 4 GiB.

The only sbt actions are the two-case differential suite followed by paired SV
emission.  Postcheck requires both XML test cases passing with zero failures,
errors or skipped tests; source hashes unchanged; paired module headers equal;
and test/emitter PASS markers.  Successful output hashes are recorded in a
new manifest.  No DC is started by the migration runner.

At preflight the EDA server has about 42 GiB available memory and 584 GiB disk.
RD1 and another independent DC job remain active.  No shared workspace,
frozen source, generated input or running synthesis script is overwritten.

Bash syntax, embedded Python syntax, help and `git diff --check` pass.  Native
test acceptance is deferred to this new remote run; source compilation and
the prior interrupted attempts do not substitute for it.
