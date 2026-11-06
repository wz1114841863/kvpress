# WCG1 simulation latch repair and matching-tool preflight

Disposition: **model repair and minimal gates PASS; wrapper retry pending**.
Predecessor: `dc_wcg1_wrapper_functional_result_20261106.md` (preserved r1,
baseline 4/4, candidate four simulator-build failures, outer exit 1).
Evidence: `dc_wcg1_wrapper_model_repair_20261106.json`.

The only Chisel hardware-source delta from implementation `82bd953` is the
simulation-only latch assignment `enable_low <= enable` -> `enable_low = enable`.
The transparent-low condition, output clock expression and native CKLNQD1
SYNTHESIS branch are unchanged. The wrapper, both enables, registers, tables,
all handshake/state owners and all eight test cases are byte-identical to r1.
Production remains default-off. No timing constraint or clock period changes.

## Minimal checks completed

Local and remote installed Verilator identify as the same
`5.041 devel rev v5.040-350-g6ec5c85be`. The repaired preflight reproduces the
old COMBDLY fatal with the old assignment, then actually builds a minimal
fixed Verilator executable with the ordinary warning policy. No warning
suppression is added; the fixed build emits no Verilator warnings/errors.

The executable tests actual gated 79/80-bit word captures against root-clock
enabled reference registers, in direct-input and root-registered-source modes:

- 6,156 comparison checkpoints and 1,634 checked edge events pass;
- low-phase enabling and high-phase data/enable changes preserve pulses;
- source data/enables changing through NBA at the root edge retain the
  reference capture behavior;
- independent member/suffix enables retain their separate words;
- deliberately substituting bare AND fails with `unexpected_positive_edge`;
- deliberately merging suffix enable fails with `suffix_capture_mismatch`.

Icarus uses the hash-pinned native library model and the actual inline source.
Behavioral and SYNTHESIS binding each pass 368 native gate comparisons with
nominal 2-ns root clock, including same-root-edge NBA enable changes and
positive/negative full-pulse assertions. Native model SHA-256 remains
`4aac97c4efda0665cdc8af807a1f5f6706f69a2359453b244562cd8158f27cbf`.
These are unsdf logical edge/model checks, not measured setup/hold or proof
of every generic wrapper trace.

## Retry guard and scope

`tools/check_wcg1_wrapper_gate.py` now reproduces the old failure and requires
a warning-free executable, capture/edge checks and both negative controls
**before** any expensive remote wrapper compile. The native-library edge
checks above are additional local checks; remote preflight repeats the
matching-Verilator checks without needing Icarus/vendor-model compilation.

The new version of `run_wcg1_wrapper_validation.sh` requires this preflight,
pins its four auxiliary sources and checks their hashes after the test run.
The existing baseline four cases and candidate four differential cases then
run unchanged under the same bounded build settings. There is no weakened
assertion, skipped case, relaxed warning policy or replacement for functional
acceptance. Both XMLs and final postcheck/run/outer markers are still required.

A new immutable source archive/workspace and independent WCG1 tmux window
will be used; original r1 remains unchanged. RD2 stays excluded. This task
does not inspect or operate on RD1+PM1's process, window, inputs or log and
does not run DC, STA or the combined full successor. Native wrapper setup/
hold at the original 2 ns and generated-source closure remain later gates.
No new area, PPA, physical signoff or system/net hardware benefit is claimed.
