# WCG1 cost and edge-equivalence feasibility — 2026-11-06

## Disposition

WCG1 is **feasible as a library-cell storage candidate**, with positive
priced-cell arithmetic and a passing zero-delay edge unit test. It is not
yet an accepted replacement for the complete generic wrapper. Gated-clock
propagation, gate-enable timing and data hold must close under the unchanged
external constraints before implementation acceptance.

The candidate retains all bank/ordinal data, separate member and suffix write
enables and every combinational read. It needs no ST1 global ordinal-nonreuse
assumption, capacity reduction or extra admission/read handshake. Unlike the
ST1 aliasing issue, its remaining qualification concerns implementation timing.

This batch adds a test-only library-cell bench, checker and library-only
metadata probe. Production Chisel/RTL, generated inputs, constraints,
Full-KV/Route-A tops and RD2 remain unchanged. No analyze/elaborate/link/map/
compile of a design or full paired DC is run. The remote DC invocation reads
only the existing target library and writes metadata in a separate run root.
The Verilog compilation is for a small local simulation, not synthesis.

## Native library/input closure

The accepted remote probe is:

```text
tmux:    kvzap-wcg1-p0:lib-cost (probe finished; shell retained)
run:     wcg1_library_cost_probe_20261106_r3
root:    /home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/
         wcg1_library_cost_probe_20261106_r3/
```

Its native metadata PASS, native exit 0, postcheck PASS and outer exit 0 are
present. All metadata files and the native log are error-free and input hashes
recheck. No RD2 window, run input or process was queried or changed.
The sourceable environment, target library and scalar cell definitions remain
the existing fair-v1 choices, not a new library or a relaxed Route-A clock.

| Item | SHA-256 |
|---|---|
| target DB | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| companion functional model | `4aac97c4efda0665cdc8af807a1f5f6706f69a2359453b244562cd8158f27cbf` |
| native 16-cell TSV | `6474144fd46f259c9529719b92b3698acc0b86b75608bdfd7e201078948cf3f4` |
| library-only Tcl | `fe515c5fed9c3f5cbc1884325091bf8cb449c379344718b8a5d07924c8ebdcbf` |
| library runner | `e72195e91f5253baf3c0932ae7ca1bc03ff41d6e077139702ab3c82fbf9d2ece` |

The local accepted edge result is
`analysis/experiments/wcg1_feasibility_20261106_r4/result.json`, SHA-256
`2ad273a2b154739391bfbf566f2d7c6d5b162aa13d3c8706d1a40057e1e1b546`.
Local copies of the accepted native probe are retained under
`analysis/experiments/wcg1_feasibility_20261106_r2/native_probe_r3/`.
Large vendor models and simulator images remain ignored artifacts, not Git
sources. Tracked result companion:
[`dc_wcg1_cost_edge_feasibility_20261106.json`](dc_wcg1_cost_edge_feasibility_20261106.json).

## Actual gate price and load check

| Cell | Native area | Relevant native capacitance data |
|---|---:|---|
| `EDFQD2BWP12T30P140LVT` | 3.528 | clock input 0.000706 |
| `DFQD2BWP12T30P140LVT` | 2.520 | clock input 0.000520 |
| `CKLNQD1BWP12T30P140LVT` | 2.520 | output max capacitance 0.067370 |

Capacitance comparisons use the same native library units; no unit conversion
or wire-load estimate is invented. The gate is characterized as
`latch_posedge_precontrol`. Test enable TE is tied low in the unit bench.
Explicit dont_use is true for gate D20/D24; missing/unset dont_use on the
smaller candidates is recorded UNKNOWN, not elevated to complete mapping
eligibility. The selected D1 model and DB object are available.

Bare clock-pin load is 79 x 0.000520 = 0.041080 for a member word and
80 x 0.000520 = 0.041600 for a suffix word. Both are below the D1 gate's
0.067370 output max-capacitance value, **without wire load**. This is only a
load feasibility check: it does not prove transition time, clock latency,
gate-enable setup/hold, pulse-width or complete timing closure.

Uniform D2 data cells and one D1 gate per enable group give:

| Component | Cell-only area arithmetic |
|---|---:|
| 366,336 enabled DFFs | 1,292,433.408 |
| 366,336 ordinary DFFs | 923,166.720 |
| 4,608 word clock gates | 11,612.160 |
| candidate data + gates | 934,778.880 |
| difference before all other costs | 357,654.528 |

That difference is 27.673% of the modeled table-cell sum and 10.555% of the
accepted RD1 top area. **This is not mapped-area improvement.** It excludes
clock/data buffering, wires, gate/FF resizing, hold repair, real enable
distribution and mapping-policy effects. The uniform-cell assumption is not
a new per-bit reference-count audit of RD1. No clock-power saving or physical
clock-tree benefit is measured.

## Why the functional structure can preserve generic semantics

For each bank b and ordinal o, use the original write conditions:

```text
E_member[b,o] = accepted_admission && admission.layer == b
                && admission.ordinal == o
E_suffix[b,o] = E_member[b,o] && pending_binding_offered
```

The original bit transition on the root rising edge is
`Q_next = E ? D : Q`. A proper positive-clock gate holds the enable while
the clock is high and permits a rising gated edge only for the selected
write. With the gate's enable capture and the data flop's setup/hold satisfied,
the ordinary DFF performs the same edge update. In the ideal zero-delay
functional model that edge is in the same simulation time as the root edge.

The following invariants are required, not optional optimizations:

- Member and suffix groups have distinct gates/enables. Unbound admission
  changes member data only; suffix data must remain intact even after a claim
  or reset invalidates its presence, because data Regs are not resettable.
- Presence, generation, publication and authority registers remain on their
  existing control path. Do not feed a gate-open/busy state into ready.
- All words keep independent state and read wires. Stopping a word's write
  clock does not stop reading its Q outputs. Independent M/C/F/B/S/O reads,
  valid-low C.ready, and cross-bank same-ordinal values need no new arbiter.
- Reset/init must not add data-array clearing or reset-mask an originally
  enabled data write. The original visibility rules, not zero initialization,
  protect uninitialized cells.
- Under the storage relation, every original combinational consumer sees the
  same settled record values and unchanged control predicates. This gives a
  composition argument for unchanged handshakes; it is not a completed
  whole-wrapper proof or a promise of identical analog propagation delays.

There is no earlier-cycle enable reservation, journal aliasing, new read
latency or producer obligation in this functional organization. Actual timing
must be met by the implementation under the original numerical I/O/clock
contract, not by requiring stronger external data/enable timing silently.

## Native functional-cell unit verification

The bench is `hardware/route_a/dc/tests/wcg1_storage_edge_tb.sv`; runner is
`tools/check_wcg1_feasibility.py`. Eight independent rows contain full 79/80-bit
words, reference enabled DFFs and candidate ICG + ordinary DFFs. Four member
read indices and an independent simplified suffix-ready/valid probe remain
available. The latter is not the complete production C validation cone.
The source word enables are modeled as the already accepted admission event
and the binding qualifier; the real R3 join/decoder is not instantiated.

Accepted r4 runs 978 storage/read comparisons and 552 logical gate-edge
monitor checks, with exit zero and `WCG1_EDGE_UNIT_PASS`. Cases include:

- independent row selection and continuous reads during writes/idle;
- bound/unbound writes, absent valid/ready and retained suffix values;
- late-low-phase enable assertion/deassertion, high-phase enable/data changes;
- root-edge NBA source-data changes in the ideal functional model;
- walking every member/suffix data bit, including both 64-bit field high bits;
- control reset without erasing data, including the raw unreset data-Reg write
  rule when E is asserted during reset (not a new legal DUT traffic claim);
- 256 deterministic mixed-write/read cycles and a valid-low readiness probe.

The tests use the actual pinned companion cell model and its storage
primitives. Icarus does not enforce native setup/hold checks or SDF delays here;
unsupported edge-sensitive specify warnings are retained. Thus PASS is a
functional cell-unit result, not a timed simulation or formal proof. Eight
rows do not establish full-wrapper 36 x 64 integration or all parameter profiles.

Three controls must differ:

| Control | Expected observed failure | What it establishes |
|---|---|---|
| BARE_AND | new high-phase clock edge | arbitrary `clock & enable` is not the proposed implementation |
| MERGED_ENABLE | old suffix overwritten on an unbound write | separate enables are necessary |
| CLOCK_SKEW | new value captured after root-edge NBA change | ignoring gated-clock/data hold is unsafe |

All exit nonzero at their intended checks and are retained as expected
negative/diagnostic evidence, not failing positive candidates.

The CLOCK_SKEW case inserts an artificial 50-ps downstream clock delay and
lets source data change at the root edge in NBA scheduling. It is **not** a
measured gate delay, an annotated PDK corner, or proof of a physically legal
input trace violating WCG1. It demonstrates the hold dependency that ideal
simulation cannot discharge. The reference's and candidate's real hold/setup
requirements still need native timing with actual paths and propagated clocks.

## Failures preserved and postcheck repair

- Library launch r1 stopped before DC because the remote workspace lacked
  the assumed sourceable environment path. The successor uses an explicit,
  separately hash-pinned environment file in bundles; no workspace sync occurs.
- Probe r2 obtained valid scalar cell attributes, but report_lib printed
  LCSH-3 into a redirected report because Library Compiler is unavailable.
  The initial postcheck looked only at native.log, so its outer zero marker
  was insufficient. This run is rejected as clean metadata closure and retained.
- Probe r3 removes that unsupported report command and scans every metadata
  file as well as native.log for Error/Fatal. Native/PASS/outer/input/artifact
  closure now passes. Four regression tests in
  `tests/test_wcg1_library_postcheck.py` pass, including the redirected-error
  case that defeats the old false PASS.
- Local r1--r3 are retained precursor unit results. R4 adds explicit logical
  gate-edge monitoring; it is the current accepted unit result.

## Next acceptance gate

Proceed only as a candidate for an independently scoped mapped bank/word
screen. Before production integration it needs:

1. The actual R3 enable/decoder context or a justified characterized boundary,
   native library gate binding and complete charged read/write circuitry.
2. A matched baseline/candidate mapping with the same library and unchanged
   2.0-ns fair-v1 numerical constraints. Keep global compile methodology paired;
   do not enable a Route-A-only optimizer and compare to untreated Full-KV.
3. Explicit gated-clock propagation and gate-enable setup/hold/pulse checks,
   including root-launched data versus delayed gated capture. An ideal-clock
   report alone would hide the risk demonstrated by the skew diagnostic.
   Any supplemental timing methodology must be documented and applied fairly;
   no false paths, multicycles or relaxed Route-A clock may manufacture closure.
4. Full generic-wrapper functional/source/port/driver closure, preserving
   independent validation, unbound capacity, entry_id drivers and all R3/R6/R2
   semantics. A priced cell unit is not permission to black-box parent control.

No mapped screen is launched by this assessment. The disposition is
`library_input_pass + zero_delay_edge_unit_pass + priced_cell_direction_positive
+ wrapper_integration_not_run + gated_timing_open`. No PPA, zero external
cost, speedup or hardware net-benefit claim follows. RD2 remains independent.
