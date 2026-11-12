# WCG1 real-wrapper r2 mapping and gated-clock STA — audited result

Run `wcg1_wrapper_mapping_sta_211f1e2_20261106_r2` completed successfully.
Accept **the isolated actual-wrapper mapping/STA screen**: input/tool/artifact
closure passes, matched hold-pass cell area falls **15.624812%**, and both
sides report zero setup/hold violations at the unchanged 2 ns. The gated
candidate has **0.000000 ns worst setup slack**, so this establishes no
positive setup margin. Structural cleanliness remains open.

This audit reads only WCG1 r2 artifacts and its named tmux. It runs no DC,
simulation or replacement experiment and changes no RTL or frozen input.
RD1+PM1 is neither inspected nor modified. Its full-run result is not inferred
here. RD2 remains excluded, and production WCG1 defaults remain off.

Launch authority: [研究过程与结果（H4）](hardware_reports/04_area_timing_optimization_and_design_review.md)
and JSON; methodology:
[matched wrapper plan](dc_wcg1_wrapper_mapping_plan_20261106.md).
Independent evidence and report hashes:
[`dc_wcg1_wrapper_mapping_retry_result_20261107.json`](dc_wcg1_wrapper_mapping_retry_result_20261107.json).
Original r1 preflight exit 7 and its logs/archive remain preserved.

## Completion, provenance and native binding

The reference and gated native exits and persisted statuses are 0. Both
native side PASS markers and all four raw/repaired stage markers are present.
Postcheck PASS, run PASS, outer exit 0 and root `exit_status=0` all agree.
The named `kvzap-wcg1-wrapper-map-r2:paired-sta` pane remains as idle bash;
pane existence is not the completion criterion. No native Error/Fatal occurs
in the preflight, side logs or redirected reports.

The independent read-only checker reproduces the saved result, including
all **73** native artifact hashes. The **130** frozen source/script files,
internal freeze/checksum manifests, prepared sources/filelists, versioned
runner, source archive and target DB rehash against the launch pins. All 130
local counterparts also retain those frozen hashes. There is no input drift.

| Pinned item | SHA-256 |
|---|---|
| Source/script archive | `aebd5a0716e1899fef5ec56ad82cacd92367b4704d4cb4b63e799babe9cdfdd4` |
| Runner | `430a928183415656cf81d51bb27da557c61cf28d60c71681657720229ee23022` |
| Target DB | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| Prepared input manifest | `2e5101daa20fed6a1b134e5ed7a29a013a0f07778eea37484cbb64cef560e2e1` |
| Native mapping result | `f13bb121c136ee643d0ce1c564096fd55cf87a0ac55dedc6373c12606e3f0f56` |

The prepared inline file exactly matches the frozen helper string. The
error-free native preflight links **4,608 CKLNQD1BWP12T30P140LVT cells**, all
E pins and the characterized `latch_posedge_precontrol` cell. The corrected
shared-instance sizing command succeeds. Both candidate mapped netlists
retain all 4,608 native gates, with CP/E/TE/Q present and TE driven by native
TIEL cells; the pinned companion model defines their constant-zero output.
Actual capture paths include positive native gate Q delays, e.g. **0.023367
ns**, rather than an idealized zero-delay gate.

Source field/row and mapped-instance checks independently retain **366,336
table bits**: 182,016 member bits and 184,320 suffix bits, including both full
64-bit fields. All other declared parent state and typed top headers match.
Reference table bits map to EDFQD2; candidate table bits map to DFQD2. All
48 authority/publication entry_id output bits retain drivers in all four
snapshots. This is no capacity reduction or source-level state deletion.

Exactly the same P3 array-interior proxy is used on each side. Its bytes,
protocol implementation and physical peripherals remain nonzero/unestimated
outside this screen's mapped cell area. Real parent control is retained.

## Measured cell area and its source

Area values below are native library cell-area units; they are not a physical
core area or a whole-chip measurement.

| Snapshot/component | Reference | WCG1 | Reduction |
|---|---:|---:|---:|
| Raw total | 2,294,423.081761 | 1,933,940.727897 | 15.711242% |
| Matched hold-pass total | 2,295,026.201759 | 1,936,432.671921 | **15.624812%** |
| Hold-pass noncombinational | 1,404,039.717318 | 1,046,378.419620 | 25.473731% |
| Hold-pass combinational | 890,986.484441 | 890,054.252301 | 0.104629% |

The measured net saving is **358,593.529838**: 357,661.297698 in
noncombinational area and 932.232140 in combinational area. The main mechanism
is replacing per-bit enabled flops with ordinary flops and one native gate
per member/suffix word. The native gate, tie cells, parent decode, buffering,
resizing and repeated hold-pass costs are included in these totals.

The identical `set_fix_hold` / `compile -only_hold_time` pass increases
reference area by 603.119998 and candidate area by 2,491.944024. Raw hold
already passes in this actual-wrapper experiment; those costs are changes
made by the common pass, not proof that it repaired prior hold violations.
Their inclusion reduces the apparent raw saving by 1,888.824026. The final
15.624812% is therefore the appropriate matched result, not the older bank
screen's 16.5262% or a 36-bank extrapolation.

The native root-net fanout falls from **400,110 to 38,382**, a structural
reduction of 361,728 direct loads, exactly `366336 - 4608`. Data clock loads
now sit behind the word gates. Their downstream clocks/buffers still exist.
Both roots remain high fanout, and DC substitutes a 1,000 fanout for delay
calculation (`TIM-134`; reported root load 1001 on both). This is not a
measured clock-tree capacitance, clock power, CTS result or 90% energy saving.

## Setup, hold and gated-clock checks

Both sides use the same original 2-ns numerical profile: setup/hold uncertainty
0.10/0.02 ns, I/O delay 0.20 ns, input transition 0.05 ns and output load
0.005 pF. Reset remains timed; no false/multicycle exceptions are introduced.
Both propagate actual clock-cell arcs under the declared isolated-screen
policy. The saved SDCs independently pass the constraint checker.

| Hold-pass timing metric | Reference | WCG1 |
|---|---:|---:|
| Worst setup slack | +0.000037 ns | **0.000000 ns** |
| Setup WNS / TNS / violating paths | 0 / 0 / 0 | 0 / 0 / 0 |
| Worst hold slack | +0.029539 ns | +0.029539 ns |
| Hold WNS / TNS / violating paths | 0 / 0 / 0 | 0 / 0 / 0 |
| Native gate-enable setup slack | — | +0.740547 ns |
| Native gate-enable hold slack | — | +0.211413 ns |
| Worst reported gated-data capture hold slack | — | +0.114801 ns |

Raw and matched hold-pass timing metrics agree. Native scalar reference
setup slack is `3.65973e-05` ns; candidate scalar setup slack is exactly `0`
as reported. Neither has meaningful positive setup headroom at this boundary.
The candidate worst setup path runs from `stageValidRecords_2_reg[0]` to
`io_authority_transition_out_bits_entry_id[20]`; it is not a gate-enable
failure. Worst gate setup runs from an admission logical-position input to
`suffixGate_2187/native_gate`; worst gate hold runs from `initialized_reg`
to `memberGate_1096/native_gate`.

This accepts the reported isolated single-corner DC setup/hold screen. It
does not establish whole-top timing, physical hold safety, extracted wiring,
clock-tree skew or multicorner signoff. There is no timing-speedup claim.

## Structural cleanliness and disposition

No LINT-3/LINT-5 or missing entry_id driver is found. `check_timing` contains
no coverage warnings. Nevertheless, both sides retain identical native
cleanliness issues after the common pass:

| Native category | Count on each side |
|---|---:|
| LINT-28 unconnected ports | 4,052 |
| LINT-29 feedthrough | 407 |
| LINT-31 shorted outputs | 667 |
| LINT-33 multiple pins on a cell | 43 |
| LINT-52 constant outputs | 560 |
| LINT-55 P3 proxy information | 1 |
| `min_capacitance` violations | **554** |

There are **5,729 Warning lines plus one LINT-55 Information entry** per
side after the pass (5,914 warnings plus one proxy entry raw). Frozen
`mapping_result.json` counts each LINT token in the summary header as well
as the detail entries, so its category values are each one larger. The table
above uses the native summary/detail counts; the saved result is preserved.
No checker or frozen report is rewritten to normalize that presentation.

The min-capacitance report contains 554 zero-load nets with required
capacitance 0.000410 and reported slack -0.000410, aggregate -0.227141.
These exist equally in raw/repaired reference and candidate; they are not
setup/hold time violations. QoR's zero max-cap/max-transition violations
does not clear them. Do not relabel the result as constraint-clean or waive
them without a separate review. Existing typed unused/feedthrough/constant
ports and the approved P3 proxy remain visible; WCG1 provides no lint benefit.

Tool/input closure **passes**; actual isolated mapped area **improves**;
reported 2-ns setup/hold **passes with zero setup margin**; structural
cleanliness **remains open**. The earlier directed functional acceptance
remains 8/8; no additional functional simulation or universal equivalence
proof is claimed in this audit. All 36 local input/postcheck regressions
pass, together with local receipt consistency and `git diff --check`.

WCG1 is now a supported candidate for a later, separately authorized cumulative
integration/freeze and full paired DC. This audit starts no such job. Do not
subtract this isolated saving from accepted RD1 full-top area or update its
146.747x ratio. PM1 composition, parent context and the full mapping must be
measured together before any new overall ratio. PPA, zero-cost external
services, system acceleration and hardware net benefit remain unestablished.
