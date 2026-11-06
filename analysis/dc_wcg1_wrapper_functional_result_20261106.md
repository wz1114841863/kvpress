# WCG1 wrapper validation r1: simulator build failed, not accepted

Run: `wcg1_wrapper_82bd953_20261106_r1`.
Disposition: **FAILED_CANDIDATE_SIMULATOR_BUILD_NOT_ACCEPTED**.
Input/provenance closure passes, but the eight-test acceptance gate fails.
Evidence:
[`dc_wcg1_wrapper_functional_result_20261106.json`](dc_wcg1_wrapper_functional_result_20261106.json).
Original launch and contract remain in
`dc_wcg1_wrapper_functional_launch_20261106.md` and
`dc_wcg1_wrapper_isolation_20261106.md`.

## Completion and test results

The WCG1 job has ended and its tmux pane is back at the shell. The total log
and result-root exit file both report outer exit **1**. Source/Test compile
passed, followed by two completed suites, eight registered tests, four
succeeded and four failed, with zero cancelled/ignored/pending. The suite
stage took about 16 minutes 47 seconds.

| Suite | Cases | Passed | Failed | Actual outcome |
| --- | ---: | ---: | ---: | --- |
| `RouteARTL39AMaterializationSpec` | 4 | 4 | 0 | baseline regression passed |
| `RouteAWCG1WrapperSpec` | 4 | 0 | 4 | candidate simulator construction failed |

Both XMLs independently report zero errors/skips. Their four case names
match: exact bound materialization/sidecar/reservation; matching-fault
release; packed-write sequence and matching terminal; and unbound joins,
authority stalls, duplicate rejection and bank/ordinal-63/reset behavior.
The candidate cases fail **before functional stimulus executes**. Therefore
the runner's absence of postcheck PASS, functional RUN_PASS and result.json
is correct; no partial eight-case acceptance is made.

## Exact root cause

All four candidate XML failure messages and the native log identify the same
diagnostic from Verilator 5.041:

```text
%Warning-COMBDLY: ...route_a_compact_word_clock_gate.sv:8:28:
Non-blocking assignment '<=' in combinational logic process
    if (!clock) enable_low <= enable;
... This will be executed as a blocking assignment '='!
%Error: Exiting due to 1 warning(s)
```

The affected code is the newly added **simulation-only** branch of the
inline WCG1 gate model:

```systemverilog
always_latch begin
  if (!clock) enable_low <= enable;
end
```

Scala compilation and Chisel/firtool elaboration complete, but Verilator
rejects this model while constructing each candidate simulator. All four
candidate directories contain the expected generated gate source (identical
to the frozen inline source after removing firtool's single generated-file
comment), and none contains the simulation executable. This identifies the
failure layer as simulator construction, not a candidate output-equivalence
assertion, protocol timeout, OOM, DC mapping or setup/hold result.

The model was introduced by the WCG1 integration implementation. Preparation
checked Scala compilation and Icarus/native-gate edge comparisons, but did
not run a minimal matching-Verilator build preflight. Those earlier checks
did not cover the specific diagnostic that blocked this run.

## Input and artifact audit

The accepted archive SHA-256 rechecks to
`acae22189e4b254c95316101f262d0f6e122dac5290de43981ce35f47ddb1f15`;
runner SHA-256 rechecks to
`5f84e073d1f850006745c1b84dd51d38f450cca6b8e4573bb40027b00dc14a0f`.
All 122 frozen source hashes match, and the input manifest matches its
launch-time pin. The three RD2 helper/spec/emitter files remain excluded.
Fetched logs, exit marker and both XMLs match independently computed remote
hashes. The linked JSON retains each case, failure stage, generated gate
source hashes and absence of candidate executables.

No source, runner, archive, old output or tmux layout was edited. No test was
restarted, no DC/STA tool was invoked, and the separate RD1+PM1 process,
window, inputs and logs were not accessed. Its state is not re-audited here.

## Interpretation and repair gate

The baseline wrapper passed all four directed tests. The WCG1 actual-wrapper
functional/differential gate remains **unverified**: the candidate did not
reach simulation, so the four failures supply neither passing equivalence
evidence nor a functional mismatch trace. More issues may appear after this
build blocker is repaired; no broader correctness assumption is justified.

The earlier accepted 16.5262% area reduction belongs to the independent
matched single-bank mapped/STA experiment. This build failure does not change
that historical result and supplies no new wrapper area or timing evidence.
Production WCG1 remains default-off; combined full DC is not authorized by
partial test success. Real-wrapper native clock binding, generated closure
and propagated-clock setup/hold at the unchanged 2 ns remain open.

The next minimal step is to reproduce this diagnostic in a small Verilator
model, repair the simulation representation while retaining the native
SYNTHESIS binding, then verify edge/full-pulse behavior against the native
cell before a new immutable eight-test retry. A syntax/assignment change
requires fresh checks for root-edge and low/high-phase enable transitions;
the warning's proposed execution behavior alone is not equivalence proof.
This repair needs no repeat of the completed single-bank DC or interruption
of the separate RD1+PM1 run. This inspection performs no such repair/retry.

No complete wrapper functional closure, new area benefit, hardware timing
closure, PPA, external-service zero cost, speedup or net hardware benefit is
claimed.
