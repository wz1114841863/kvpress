# Compact-membership paired DC result — 2026-11-04

## Scope and completion

Run `dc_feasibility_fair_m2p3_compact_20261103_r1` completed in tmux
`kvzap-control-refine:p10-compact-dc` with pane status zero.  Its retained log
`m2p3_compact_p10_dc_20261103.log` contains both per-top exits zero, paired
`KVZAP_DC_FEASIBILITY_RUN_PASS`, and `KVZAP_M2P3_COMPACT_P10_DC_EXIT=0`.
Both tops emitted nonempty DDC, mapped Verilog, QoR, hierarchy area, setup/hold,
constraint, check-design/check-timing, port, reference and proxy-instance reports.

The immutable run root is:

```text
/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/
  dc_feasibility_fair_m2p3_compact_20261103_r1/
```

The original baseline is `dc_feasibility_fair_r5desc_20261029_r1`; the immediate
predecessor is `dc_feasibility_fair_control_refinement_20261102_r1`.
This comparison retains identical fair-v1 numerical constraints (including
2.0-ns clock), library, top scopes, 1/48-file lists and five array boundaries.
Static coverage passes with no unconstrained ports.  Native postcompile
check-timing reports no missing input delay or unconstrained endpoint.
Each approved proxy is reported exactly once and parent controls remain mapped.

## Input and artifact closure

Live hashes were recomputed and match the copied input identities:

| input | SHA-256 |
| --- | --- |
| paired archive | `61d4e51cafea3c96167f371c41b31af051ca5844fd93f58ccba127b681cf7008` |
| target library | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| constraint Tcl | `3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007` |
| proxy manifest | `de6cd6023138cba8974dd70aa043b864e1819db79cf04148c852108a38f98e6d` |
| proxy materialization | `0c496d0fc56f335babfd6f42d047a10e08a9db54fbb6885c1e23580d7bb280be` |
| proxy check | `6f2b2389bcbcc95d7bf77fb1da9bb0f040a7ca6331f73ea35e44bfa82d951bc2` |
| run constraint manifest | `6ce1df2486e663eb0921cfea225ec003afcb68f8be52aab099daa65ec24c6de6` |

| output | SHA-256 |
| --- | --- |
| Full-KV DDC | `5bb1a3136a47bb36f0e4115b02f84accdcb2b7e56ccde5958fecf8cc9f934093` |
| Full-KV mapped HDL | `354a2cf4a74f6ba4dfd6140bdc0c7b5506dc9e2c12e92278cb52ab2b0b749419` |
| Route-A DDC | `b2908d013cc7182aec8b2c31e8dd77a360a751ac3f12a56f6983df3c03209e69` |
| Route-A mapped HDL | `33c57f18db645763ed22ce43a06946b202ecfd60961b536916cc2c4e7c7940f4` |

Full-KV exactly reproduces area 23,091.432498, 5,060 sequential cells, zero
setup/hold violations and 3,010 postcompile Warning records.  Its mapped HDL
is identical to the predecessor after excluding the generated date line.
The previously retained Full-KV verification-include VER-41 diagnostic repeats;
it is not evidence of a newly introduced Route-A failure.

## Observed mapped area

| metric | original | first refinement | compact membership |
| --- | ---: | ---: | ---: |
| cell area | 6,716,537.642416 | 3,952,935.893452 | 3,624,318.814461 |
| sequential cells (QoR) | 1,298,150 | 653,138 | 577,106 |
| combinational cells (QoR) | 3,080,274 | 2,436,750 | 2,353,258 |
| combinational area | 2,201,809.163004 | 1,709,334.807431 | 1,644,423.975866 |
| noncombinational area | 4,514,728.479412 | 2,243,601.086021 | 1,979,894.838595 |
| Route-A / Full-KV cell area | 290.867x | 171.186x | 156.955x |

Relative to the first refinement, observed cell area falls 328,617.078991
(8.313%), sequential cells fall exactly 76,032 (11.641%), combinational area
falls 3.797%, and noncombinational area falls 11.754%.  The sequential delta
exactly matches the pre-DC redundant-field accounting, rather than the much
larger 589,824-bit raw HDL reduction.  Cumulative observed area reduction from
the original is 46.039%.

| hierarchy | first refinement | compact membership | interpretation |
| --- | ---: | ---: | --- |
| M2/P3 wrapper | 2,968,610.1130 | 2,636,842.5298 | -11.176%; dominant reduction |
| metadata-admission bridge | 85,832.8811 | 85,833.3851 | effectively unchanged |
| page manager | 407,417.9746 | 407,440.9906 | effectively unchanged |
| M2 control | 176,327.4263 | 178,531.4185 | small mapping increase |

Wrapper combinational area changes from 1,265,427.0685 to 1,202,242.9409;
noncombinational area changes from 1,674,027.4848 to 1,405,170.1892.
The wrapper still dominates at 72.8%, followed by page manager at 11.2%.
These are observed tool numbers; the new undriven-output issue below prevents
unqualified acceptance of the mapped successor as structurally closed.

## Timing

| setup metric | original | first refinement | compact membership |
| --- | ---: | ---: | ---: |
| WNS (ns) | -0.31 | -0.33 | -0.31 |
| TNS (ns) | -7,318.06 | -7,891.18 | -8,564.11 |
| violating paths | 34,814 | 31,458 | 35,671 |
| logic levels | 126 | 126 | 131 |

WNS improves 0.02 ns over the immediate predecessor, but TNS magnitude worsens
8.528% and violating paths increase 4,213 (13.392%).  Hold remains zero-violation.
This is not timing closure or an overall timing improvement.

The worst reported startpoint is now an arbiter candidate-slot pending
descriptor reference; the endpoint remains sidecar-read-issue ready.  Many
other paths end in M2/P3 materialized-member or stage-state registers.  A
page-manager allocated-line-to-reclaim-line priority path also appears among
the 20 reported paths.  These support further selector/ready-path diagnosis,
not a claim that any one candidate will close timing.

## Clock load and fanout

A separate read-only saved-DDC query completed with tmux pane status zero and
`PROBE_READ_ONLY_COMPLETE`.  It performed no compile or design write.  Its
log is `compact_result_readonly_probe_20261104.log` in the Chisel project logs
directory, outside the immutable run root.

`all_high_fanout -nets -threshold 1000` identifies exactly the expected-fragment
count bit and `clock`.  Native report-net gives fanout 3,070 and 577,110,
respectively.  Compared with predecessor counts 3,074 and 653,142, the clock
load falls exactly 76,032.  The latter equals QoR sequential cells plus four,
consistent with the prior transient-clock-alias diagnosis.  Both high-fanout
conditions remain; this is logical fanout evidence, not a physical clock tree
or power result.

## Structural cleanliness and new regression

| Warning class | first refinement | compact membership |
| --- | ---: | ---: |
| all Warning records | 44,513 | 44,585 |
| LINT-28 unconnected ports | 13,671 | 13,671 |
| LINT-29 feedthrough | 22,526 | 22,528 |
| LINT-31 shorted outputs | 7,113 | 7,112 |
| LINT-33 same-cell multi-pin | 281 | 280 |
| LINT-52 constant outputs | 922 | 922 |
| LINT-3 undriven nets | 0 | 24 |
| LINT-5 undriven outputs | 0 | 48 |

Four approved array black-box LINT-55 entries also remain in the summary;
they are not Warning records in the table's counting convention.

The new 24 undriven nets and 48 undriven output bits all concern the 24-bit
`entry_id` on M2/P3 authority-transition and publication-member outputs.  Raw
generated HDL contains the full coordinate reconstruction and drives both
outputs.  The mapped wrapper has only output-to-output alias assignments and
no surviving reconstruction driver.  R6's production incoming-transition
logic does not consume entry_id, and the activation binder's member acceptance
uses layer/tag/ordinal rather than entry_id.  These observations are consistent
with synthesis removing an unconsumed combinational cone across hierarchy.
They do not demonstrate an arithmetic error or a functional miscompile of a
consumed field.  The pre-synthesis 57/57 result remains valid at its own scope.

Nevertheless the mapped output has lost its explicit driver, and DC reports
logic-zero assumptions.  This is a new structural regression, not a harmless
warning-count improvement.  A bounded diagnosis must determine the correct
output-observability/driver treatment and validate it without introducing fake
semantic consumers, deleting required fields or restoring unnecessary record
state merely to silence lint.  A repaired successor needs its own checks;
this run must be preserved as diagnostic evidence.

The existing LINT-28 roots remain: lifecycle adapter 4,147, page manager 1,069,
and wrapper 528.  Native check-timing still reports two high-fanout nets.

## Separate verdicts

1. Tool/input closure: PASS for execution, provenance and native artifacts.
2. Mapped-area change: observed reduction of 8.313% versus the first refinement,
   with the exact expected 76,032-cell sequential reduction.  Acceptance as a
   structurally closed mapped successor is qualified by the new driver issue.
3. Timing closure: FAIL; WNS remains negative, TNS and path count worsen.
4. Structural cleanliness: REGRESSED AND BLOCKED by new LINT-3/LINT-5 outputs,
   in addition to existing warnings and high fanout.
5. Non-conclusions: no PPA, physical clock-tree/power, zero-cost external
   service, full-system area ratio, speedup or hardware net-benefit claim.

Next work should diagnose the new mapped entry_id driver issue before another
optimization or synthesis run.  This result does not authorize a rerun.
