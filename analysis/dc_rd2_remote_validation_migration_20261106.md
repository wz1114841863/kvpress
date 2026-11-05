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
workspace, records all source hashes, and uses the platform's proven native
Java 11, Verilator and firtool 1.158.0 environment.  Java heap is capped at
4 GiB.  Java 11 is the same runtime used by the accepted p19 contextual
generation; the Chisel simulator class files target Java 8 bytecode.

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

## First remote environment failure and correction

The first remote attempt in `p25-rd2-test-emit` verified the source hash and
available memory but failed before JVM startup.  Both exits are 1.  The
installed platform Java 21 binary requires GLIBC_2.33/2.34/2.38, unavailable
on this older server.  No test or RTL emission occurred.

That output remains at
`artifacts/rd2_remote_validation_48f8cf3_p25`, with log
`logs/rd2_remote_p25_test_emit_20261106.log` under the remote project root.
The runner now uses `/usr/lib/jvm/java-11-openjdk-amd64` by default and
executes `java -version` before extracting/compiling the workspace.  It
supports the explicit `KVZAP_RD2_JAVA_HOME` override.  The source snapshot,
test geometry/stimulus and simulator build controls remain unchanged.  Retry
uses a fresh root and window; the failed p25 root is never reused.
