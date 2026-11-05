# Compact-membership entry_id-repair paired DC result — 2026-11-05

## Scope and completion

This record closes production verification of the second Route-A control
optimization: compact M2/P3 membership records, followed only by the bounded
`entry_id` synthesis-driver preservation repair. Functional RTL, interface,
latency, admission/publication/authority/arbitration semantics and the 48-file
input archive are unchanged from the compact-membership run.

Run `dc_feasibility_fair_m2p3_entryid_repair_20261104_r1` completed normally
in `kvzap-control-refine:p11-entryid-dc` with pane exit zero and no remaining
process. The retained log contains:

```text
KVZAP_DC_FEASIBILITY_FULL_KV_EXIT=0
KVZAP_R3_ENTRY_ID_DRIVER_PASS bits=48
KVZAP_DC_FEASIBILITY_ROUTE_A_EXIT=0
KVZAP_DC_FEASIBILITY_RUN_PASS run_id=dc_feasibility_fair_m2p3_entryid_repair_20261104_r1
KVZAP_ENTRYID_REPAIR_P11_DC_EXIT=0
```

Both tops emitted nonempty DDC, mapped HDL, QoR, hierarchy area, setup/hold,
constraint, design/timing check, port, reference and proxy reports.

## Input and artifact closure

The run retains the same `dc_feasibility_fair_v1` 2.0-ns constraint profile,
TSMC28 candidate library, Full-KV input, compact 48-file Route-A archive and
five typed array proxies. Added policy is limited to the named R3 result nets.

| input | SHA-256 |
| --- | --- |
| compact paired HDL archive | `61d4e51cafea3c96167f371c41b31af051ca5844fd93f58ccba127b681cf7008` |
| target library | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| constraint Tcl | `3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007` |
| fair-v1 run manifest | `6ce1df2486e663eb0921cfea225ec003afcb68f8be52aab099daa65ec24c6de6` |
| proxy manifest | `de6cd6023138cba8974dd70aa043b864e1819db79cf04148c852108a38f98e6d` |
| proxy materialization | `0c496d0fc56f335babfd6f42d047a10e08a9db54fbb6885c1e23580d7bb280be` |
| proxy check | `6f2b2389bcbcc95d7bf77fb1da9bb0f040a7ca6331f73ea35e44bfa82d951bc2` |
| entry_id policy Tcl | `a936bd9453002fc3de7f7388aa78c3e74cf31e45a0461773105935ae0157438d` |

| output | SHA-256 |
| --- | --- |
| Full-KV DDC | `e4dde95ce7e3663932ced20102a32dd0235a29a5e9af8cf92b638da64124295a` |
| Full-KV mapped HDL | `e8cd4b34e49a6202dd6fdf9b15eb46323b3b47a55912c1a8e5de31f04279f25a` |
| Route-A DDC | `29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326` |
| Route-A mapped HDL | `03b55a63c16cbd45c632a43570e0336b2958c464efc4333cac4dd4bf32f6b397` |
| entry_id driver report | `166bdbae78e6e404274a92387f9f071eb6f9bfb86774aa5da548294d79b8ef2c` |

Full-KV reproduces area 23,091.432498, 5,060 QoR sequential cells, zero
setup/hold violations and 3,010 warning records. The retained Full-KV VER-41
verification-include diagnostic repeats historical runs and is followed by
normal production-design mapping.

## Mapped-area result

| metric | original baseline | first refinement | repaired compact membership |
| --- | ---: | ---: | ---: |
| cell area | 6,716,537.642416 | 3,952,935.893452 | 3,622,375.558791 |
| sequential cells | 1,298,150 | 653,138 | 577,106 |
| combinational cells | 3,080,274 | 2,436,750 | 2,349,468 |
| combinational area | 2,201,809.163004 | 1,709,334.807431 | 1,640,278.407905 |
| noncombinational area | 4,514,728.479412 | 2,243,601.086021 | 1,982,097.150886 |
| Route-A / Full-KV | 290.867x | 171.186x | 156.871x |

Relative to the first refinement, the second optimization reduces cell area
by 330,560.334661 (8.362%), sequential cells by exactly 76,032 (11.641%),
combinational area by 69,056.399526 (4.040%) and noncombinational area by
261,503.935135 (11.656%). Cumulative cell-area reduction from the original
baseline is 46.068%.

The repaired result is 1,943.255670 area lower than the unrepaired compact
diagnostic run (-0.054%), despite preserving the entry_id cone. Because the
synthesis interface policy changes optimization and cell selection, this tiny
difference is mapping variation, not a third optimization benefit. The valid
second-optimization comparison is against the first-refinement predecessor.

| hierarchy | first refinement | repaired compact | change |
| --- | ---: | ---: | ---: |
| M2/P3 wrapper | 2,968,610.1130 | 2,638,229.5377 | -330,380.5753 |
| metadata-admission bridge | 85,832.8811 | 85,833.0491 | +0.1680 |
| page manager | 407,417.9746 | 407,451.2386 | +33.2640 |
| M2 production control | 176,327.4263 | 175,682.9790 | -644.4473 |

The mapped saving remains localized to M2/P3, as intended. M2/P3 still owns
about 72.8% of Route-A area, and Page Manager remains about 11.2%.

## Timing

| setup metric | first refinement | unrepaired compact | repaired compact |
| --- | ---: | ---: | ---: |
| WNS | -0.33 ns | -0.31 ns | -0.31 ns |
| TNS | -7,891.18 ns | -8,564.11 ns | -8,577.41 ns |
| violating paths | 31,458 | 35,671 | 35,897 |
| logic levels | 126 | 131 | 142 |

WNS is 0.02 ns better than the first refinement, but TNS and violating-path
count are worse. Relative to the unrepaired diagnostic, the driver policy
keeps WNS unchanged while TNS worsens 13.30 ns and paths increase 226. Hold
remains clean. This is not timing closure or an overall timing improvement.

The worst path remains from arbiter outstanding-incarnation state to the
functional sidecar-read-issue ready path. Native check-timing reports no
missing input delay or unconstrained endpoint. Two high-fanout nets remain:
expected-fragment count at 3,072 loads and the transient clock alias at
577,110 loads. The clock-alias count remains sequential cells plus four.

## entry_id repair and structural cleanliness

The fail-closed gate checks all 48 output bits. Every bit has real input
startpoints, `checked_bits=48 undriven_bits=0`, and the mapped run emits
`KVZAP_R3_ENTRY_ID_DRIVER_PASS bits=48`. LINT-3 and LINT-5 are both zero.

| warning class | unrepaired compact | repaired compact |
| --- | ---: | ---: |
| all Warning records | 44,585 | 44,533 |
| LINT-28 unconnected ports | 13,671 | 13,693 |
| LINT-29 feedthrough | 22,528 | 22,526 |
| LINT-31 shorted outputs | 7,112 | 7,109 |
| LINT-33 same-cell multi-pin | 280 | 283 |
| LINT-52 constant outputs | 922 | 922 |
| LINT-3 undriven nets | 24 | 0 |
| LINT-5 undriven outputs | 48 | 0 |

The specific structural regression is closed. Some entry_id surfaces now
appear in pre-existing unconsumed-carrier/alias warning classes, consistent
with preserving the interface without inventing a semantic consumer. The
total falls by 52, but 44,533 warnings and the two high-fanout nets mean broad
structural cleanliness remains blocked.

## Separate verdicts

1. Tool/input closure: PASS, including both side exits, paired/outer markers,
   hashes, proxy instances and native artifacts.
2. Mapped-area improvement: PASS at logic-only DC-feasibility scope; the
   second optimization gives an accepted 8.362% area reduction versus the
   first refinement and the exact expected 76,032 sequential-cell reduction.
3. entry_id repair: PASS; all 48 bits have real drivers and LINT-3/LINT-5 are
   zero without changing functional RTL.
4. Timing closure: FAIL; WNS remains -0.31 ns and TNS/path count worsen.
5. Structural cleanliness: the new regression is fixed, but the design is
   still broadly blocked by 44,533 warnings and high fanout.
6. Non-conclusions: no PPA, physical clock/power, external-service zero cost,
   system acceleration, Full-KV-equivalent feature scope or hardware net
   benefit is established.
