# WCG1 model-repair eight-test retry launch

Run ID: `wcg1_wrapper_model_fix_844e586_20261106_r2`.
Status: **remote minimal gate preflight PASS; eight-test job started, not accepted**.
Repair commit: `844e58614cb87913bcf8a243e7524cd8931b7d08`.
Repair/minimal evidence: `dc_wcg1_wrapper_model_repair_20261106.md` and JSON.
Exact frozen retry inputs and remote preflight receipt:
`dc_wcg1_wrapper_retry_launch_20261106.json`.

## Minimal prerequisites completed

The actual repaired inline gate passes a matching Verilator 5.041 executable
build without warning suppression, 6,156 capture/edge checkpoints in direct
and registered-source modes, and two negative controls. Local pinned-native
cell comparisons pass 368 checks in each of the behavioral and SYNTHESIS
bindings, including root-edge NBA changes and full-pulse assertions.

The remote preflight independently reproduces old COMBDLY, builds/runs the
fixed executable and repeats the capture/edge/negative controls successfully.
Its native_modes=0 means that the remote repeats Verilator checks only;
the two Icarus/native comparisons are separate accepted local evidence.
No DC, STA, native latch inference or full-wrapper functional PASS is inferred.

## Immutable retry and independent execution

Both r1 XMLs, failure logs, source/archive and outer exit 1 are preserved.
The new archive contains the same 122 Chisel project files, excluding RD2
and old generated artifacts, plus four minimal-preflight auxiliary sources.
The only changed project source is the inline gate assignment; wrapper,
native binding and the eight test cases remain unchanged.

Source archive SHA-256:
`6565f23ec51c5c499a56c7eeb5559828935c7953ec08b51b42e5874a4a4fb965`.
Runner SHA-256:
`32090f6850a085f6cdf85045f35f02d229ca78c974ed972f234d5a49fb83746f`.
The source/auxiliary hashes in the remote input manifest match the local
freeze, as do all five sources recorded by the remote minimal preflight.

Independent tmux: **`kvzap-wcg1-wrapper-r2:functional`**.
Total log:
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/wcg1_wrapper_functional_20261106_r2.log`.
Result/workspace root:
`/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/wcg1_wrapper_model_fix_844e586_20261106_r2/`.
Archive and versioned runner are in the separate bundles directory.

Initial remote markers include `KVZAP_WCG1_WRAPPER_INPUT_PASS` and
`WCG1_WRAPPER_GATE_PREFLIGHT_PASS checks=6156 native_modes=0`, followed by
native Java 11/sbt startup. The job retains the three-GiB JVM, two active
processors, unlimited stack, one C++ build job and two Verilation jobs;
the memory preflight passes. It reruns both four-case suites and requires
the original reference miter assertions. It neither skips the old baseline
nor weakens candidate validity/ready or live-payload comparisons.

After the user reports completion, verify both four-case XMLs with zero
failures/errors/skips, source/archive/auxiliary/preflight hashes, `All tests
passed.`, postcheck tests=8, functional RUN_PASS, outer exit 0 and exit_status=0.
At this snapshot these functional completion gates remain **pending**.
The user has been notified to await completion; no automatic retry is scheduled.

RD1+PM1's processes, windows, inputs and logs were not accessed or modified.
RD2 is absent. Only the simulation representation changed; no two-nanosecond
constraint, native SYNTHESIS binding, data width, concurrency, storage state
or handshake change is made. Real-wrapper native timing/generation closure
and any later combined full DC remain separate gates. No new mapped-area,
physical timing, PPA, external-service cost or system/net-benefit claim follows.
