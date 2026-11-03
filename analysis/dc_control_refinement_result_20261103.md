# Route-A control-refinement paired DC result — 2026-11-03

## Scope and comparison

This record accepts the completed paired DC run
`dc_feasibility_fair_control_refinement_20261102_r1` against the immutable
baseline `dc_feasibility_fair_r5desc_20261029_r1`.  Both sides use the same
`dc_feasibility_fair_v1` numerical constraints and TSMC28 candidate library.
This is a logic-only DC feasibility comparison with typed array interiors
proxied.  It is not PPA, physical implementation, external-service cost,
system speedup, or hardware net-benefit evidence.

The refinement removes only the duplicate full pending-member binding ledger
from `route_a_metadata_admission_bridge`.  R3/P3 remains the full membership
owner, and pruning, admission, R3 publication, R6 authority, R2 arbitration,
page size, scheduling, and the single-record direct-pending bound are
unchanged.

## Completion and input closure

The remote run completed normally in tmux `kvzap-control-refine:p7-dc`:

```text
KVZAP_DC_FEASIBILITY_FULL_KV_EXIT=0
KVZAP_DC_FEASIBILITY_ROUTE_A_EXIT=0
KVZAP_DC_FEASIBILITY_RUN_PASS run_id=dc_feasibility_fair_control_refinement_20261102_r1
KVZAP_CONTROL_REFINE_P7_DC_EXIT=0
```

The pane is dead with status zero and no DC process remains.  Both tops emit
nonempty DDC, mapped Verilog, QoR, hierarchy-area, setup/hold timing,
constraint, `check_design`, `check_timing`, reference, port, and array-proxy
reports.

The copied and live provenance agrees:

| input | accepted SHA-256 |
| --- | --- |
| paired HDL archive | `1b5ac01cd35c77c37c6d7a08843c8554ec2458eb25cc9d7d6cafbefc873ec33d` |
| TSMC28 candidate library | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| constraint Tcl | `3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007` |
| proxy manifest | `b95eec75ac7c98e89d3b95f2ff9f9717c9564935c2d5b25bf853cefdb5a045c9` |
| proxy materialization report | `9fd34c785fdd730aeec20090103cdfc17a2b3c9e5d103bcc1f33fc99c9670c51` |
| proxy check report | `6f2b2389bcbcc95d7bf77fb1da9bb0f040a7ca6331f73ea35e44bfa82d951bc2` |

The constraint Tcl hash is identical to the baseline.  The profile keeps the
same 2.0-ns clock, 0.10/0.02-ns setup/hold uncertainty, 0.20-ns I/O delays,
0.05-ns input transition, 0.005-pF output load, synchronous timed reset, and
no false or multicycle path.  Static and DC-native checks report no missing
input delay or unconstrained endpoint.  The Full-KV and Route-A source lists
contain exactly one and 48 files respectively.  All five approved typed array
proxies appear exactly once; their parent controls remain mapped.

The generated outputs are retained at:

```text
/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/
  dc_feasibility_fair_control_refinement_20261102_r1/
```

| output | SHA-256 |
| --- | --- |
| Full-KV DDC | `6b3724adf670f2c7d30fda2527e257522ec9a79c9068e8c838e33632c3b7ad82` |
| Full-KV mapped Verilog | `7d545dbb2937e178146806a998505c9979e126313d8a612fb7719664acf0ee0c` |
| Route-A DDC | `f420cf65b3e45d3b8c6629983a89786486722a63ac4bfb799408210fc8146895` |
| Route-A mapped Verilog | `75e966d60b8cf2569e88cbce6498db50e08d742e0e867654420bdccf22f91a50` |

Full-KV reproduces the baseline QoR exactly.  Its mapped Verilog differs only
in the generated date header after ignoring that line.  The repeated Full-KV
`VER-41` verification-include diagnostic is identical to the baseline and is
followed by the same accepted production-design mapping; it remains a retained
cleanliness item rather than a new successor failure.

## Mapped-area result

### Top-level Route-A

| metric | baseline | refined | delta | relative delta |
| --- | ---: | ---: | ---: | ---: |
| sequential cells | 1,298,150 | 653,138 | -645,012 | -49.687% |
| combinational cells | 3,080,274 | 2,436,750 | -643,524 | -20.892% |
| combinational area | 2,201,809.163004 | 1,709,334.807431 | -492,474.355573 | -22.367% |
| noncombinational area | 4,514,728.479412 | 2,243,601.086021 | -2,271,127.393391 | -50.305% |
| cell area | 6,716,537.642416 | 3,952,935.893452 | -2,763,601.748964 | -41.146% |

The mapped sequential-cell reduction is exactly the 645,012-bit raw-state
reduction, but this equality is specific to this mapped successor and library
run.  It is not a general bit-to-area conversion rule.

### Target hierarchy

| hierarchy | baseline area | refined area | delta | relative delta |
| --- | ---: | ---: | ---: | ---: |
| `route_a_metadata_admission_bridge` | 2,835,164.2069 | 85,832.8811 | -2,749,331.3258 | -96.973% |
| `route_a_m2_p3_wrapper` | 2,969,003.2321 | 2,968,610.1130 | -393.1191 | -0.013% |
| `route_a_page_manager` | 407,498.9506 | 407,417.9746 | -80.9760 | -0.020% |
| `route_a_m2_production_control_owner` | 186,527.7142 | 176,327.4263 | -10,200.2879 | -5.469% |

The bridge's combinational area falls from 515,259.1882 to 27,147.6236
(-94.731%), and its noncombinational area falls from 2,319,648.9867 to
58,218.8896 (-97.490%).  The observation therefore localizes the dominant
improvement to the intended compact bridge rather than to a changed M2/P3 or
page-manager implementation.

## Clock load and high fanout

DC still reports two high-fanout nets under its fanout-1000 delay model:

| net class | baseline loads | refined loads | delta |
| --- | ---: | ---: | ---: |
| packed-read expected-fragment bit | 3,075 | 3,074 | -1 |
| transient compiler clock alias | 1,298,154 | 653,142 | -645,012 |

The second net is renamed from `directPendingIssue/net188753` to
`directPendingIssue/net176580`, is absent from both written mapped netlists,
and has exactly `sequential cells + 4` loads in each run.  This is consistent
with the saved-DDC diagnosis that it is the top clock's transient compiler
alias, not a semantic direct-pending broadcast.  The compact bridge halves
that logical clock load, but DC still reports the high-fanout condition and no
physical clock tree has been implemented.

## Timing result

| setup metric | baseline | refined | delta |
| --- | ---: | ---: | ---: |
| logic levels | 126 | 126 | 0 |
| WNS | -0.31 ns | -0.33 ns | -0.02 ns |
| TNS | -7,318.06 ns | -7,891.18 ns | -573.12 ns |
| violating paths | 34,814 | 31,458 | -3,356 (-9.640%) |

The number of setup-violating paths decreases, but WNS and TNS both worsen.
The worst reported path also moves from an arbiter request-ID register to
`io_external_core_mem_if_v1_request_valid` to an arbiter outstanding-
incarnation register to `io_functional_sidecar_read_issue_in_ready`.  The
refinement therefore does not establish timing closure or a timing
improvement.  Hold remains clean in both runs with zero hold violations.

## Structural-cleanliness result

| post-compile class | baseline | refined | delta |
| --- | ---: | ---: | ---: |
| all `Warning:` records | 56,677 | 44,513 | -12,164 (-21.462%) |
| unconnected ports `LINT-28` | 25,572 | 13,671 | -11,901 (-46.539%) |
| feedthrough `LINT-29` | 22,788 | 22,526 | -262 (-1.150%) |
| shorted outputs `LINT-31` | 7,114 | 7,113 | -1 |
| constant outputs `LINT-52` | 922 | 922 | 0 |
| same-cell multi-pin nets `LINT-33` | 281 | 281 | 0 |
| approved array black boxes `LINT-55` | 4 | 4 | 0 |

The dominant intended improvement is visible in
`route_a_m2_production_control_owner`: its `LINT-28` records fall from 11,729
to 17 after removal of the unused full-binding carrier.  The compact metadata
bridge itself rises from one to 184 `LINT-28` records because its remaining
typed compact fields are now directly exposed to the accepting owner.  Major
unchanged roots include 4,147 lifecycle-adapter `LINT-28` records, 1,069
page-manager `LINT-28` records, and 8,375 intentional R4 external-protocol
feedthrough `LINT-29` records.  Router/demux shorted-output and feedthrough
surfaces also remain.  Full-KV's 3,010 warning records and class counts are
unchanged.

The warning reduction is real and attributable, but 44,513 warnings, two
high-fanout nets, and the remaining typed-carrier/feedthrough/shorted-output
surface mean structural cleanliness is still blocked.  These counts are not
authorization to delete necessary state, collapse typed ownership, or
black-box parent controls.

## Separate verdicts

1. **Tool/input closure: PASS.** Both tools exit zero; all markers, hashes,
   filelists, proxies, DDC/netlist outputs, constraints, and native reports
   close under the same fair-v1 profile.
2. **Mapped-area improvement: PASS at logic-only DC-feasibility scope.** The
   intended bridge reduction is observed in mapped hierarchy and produces a
   41.146% Route-A cell-area reduction under the fixed comparison.
3. **Timing closure: FAIL.** Setup still violates the 2.0-ns contract; WNS and
   TNS worsen despite fewer violating paths.  Hold passes.
4. **Structural cleanliness: IMPROVED BUT BLOCKED.** Warning and clock-load
   counts fall substantially, but the remaining surfaces are not clean.

Overall disposition:

```text
tool_input_pass + mapped_area_improved
+ timing_blocked + structural_cleanliness_blocked
```

This result does not establish PPA, physical clock or wire behavior, power,
macro cost, external-service zero cost, common-cost cancellation, controller
behavior, system speedup, or KVZap hardware net benefit.  It also does not by
itself authorize another RTL refinement or another DC run.  Any next diagnosis
should begin read-only from the saved DDC and native reports while preserving
all frozen semantic owners and constraints.
