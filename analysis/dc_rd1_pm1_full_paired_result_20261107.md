# RD1+PM1 full paired DC — audited result, 2026-11-07

`dc_feasibility_fair_rd1_pm1_20261106_r1` completed both native sides and
outer execution successfully. **Tool/input closure and a 0.901596% whole-top
area improvement versus RD1 pass; setup timing regresses and structural
cleanliness remains blocked.** Neither WCG1 nor RD2 is in this input.

This inspection is read-only on the remote artifacts. No synthesis, simulation,
RTL change or integration is launched. The prior launch remains immutable:
[`dc_rd1_pm1_full_paired_launch_20261106.md`](dc_rd1_pm1_full_paired_launch_20261106.md).
Native metrics, input checks and artifact hashes are recorded in
[`dc_rd1_pm1_full_paired_result_20261107.json`](dc_rd1_pm1_full_paired_result_20261107.json).

## Completion and fair input closure

Both native `KVZAP_DC_FEASIBILITY_PASS` and side exit-0 markers are present,
followed by `KVZAP_DC_FEASIBILITY_RUN_PASS` and
`KVZAP_RD1_PM1_FREEZE_DC_OUTER_EXIT=0`. The named
`kvzap-rd1-pm1:paired-dc` pane is now idle sh. This runner uses a persisted
outer log marker rather than an `exit_status` file.

The 201 independent primary checks pass. Fresh hashes verify the target DB,
paired archive, entry_id policy, copied input records and launch freeze
reports; the frozen script archive rehashes to `ceedaf62e...`. All bundle
checksums, 48 raw Route-A unit hashes, 47 unchanged predecessor units and
Full-KV/filelist identity recheck. The five actual proxy sources and 1/48
filelists match their manifest hashes; every other compiled unit matches
the composed raw source. Native reports retain one Full-KV and four Route-A
approved proxy instances, and all **48 entry_id output bits retain drivers**.

| Frozen item | SHA-256 |
|---|---|
| Paired input archive | `0f21d81dbce8576de64f37a6b6e097a93d089fac51381047a2f9283d8574b6c5` |
| Target DB | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| Proxy manifest | `6fa694d1694692c829e438378343e023f850359ad1362501ab7a6254c3fdf8df` |
| Fair constraint Tcl | `3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007` |

The original fair-v1 numerical values and full-paired mapping policy remain:
2 ns, setup/hold uncertainty .10/.02 ns, I/O delay .20 ns, transition .05 ns,
load .005 pF, timed synchronous reset and no false/multicycle exceptions.
This is not the WCG1 isolated propagated-clock/hold-pass policy.

Full-KV reproduces RD1 and immutable `dc_feasibility_fair_r5desc_20261029_r1`
area, cell counts and setup/hold QoR exactly: area **23,091.432498**, 5,060
sequential cells and zero setup/hold violating paths. The same Full-KV
VER-41 missing verification include persists; it is retained baseline tool
diagnostic evidence, not a newly waived error. Route-A has no native
Error/Fatal. Both DDCs, mapped HDL and required reports are nonempty and
freshly hashed. Reported completion is not a warning-free tool claim.

## Whole-top area and hierarchy

Area is native library cell area, not physical core area.

| Metric | Accepted RD1 | RD1+PM1 | Change |
|---|---:|---:|---:|
| Total cell area | 3,388,597.345862 | **3,358,045.877079** | **-0.901596%** |
| Combinational area | 1,392,283.363726 | 1,379,881.942139 | -12,401.421587 |
| Noncombinational area | 1,996,313.982136 | 1,978,163.934940 | -18,150.047196 |
| Sequential cells | 577,106 | 577,106 | 0 |
| Area / Full-KV | 146.747x | **145.424x** | -1.323 ratio points |

The incremental saving is **30,551.468783**. Leaf/combinational cell counts
fall by 14,213; the state/clock-load count does not fall. Noncombinational
area changes therefore reflect mapping/cell selection rather than removal
of required registers. Relative to the immutable original area 6,716,537.642416,
the cumulative reduction is 50.003319%; this is not PM1's incremental benefit.

| Hierarchy | RD1 | RD1+PM1 |
|---|---:|---:|
| Page Manager | 407,306.5906 | **390,023.0886** |
| M2/P3 wrapper | 2,387,543.1337 | 2,398,605.2617 |
| M2 production control | 175,735.2263 | 175,705.3224 |
| Metadata bridge | 85,833.3851 | 85,833.3851 |

Page Manager saves 17,283.5020 (**4.243364%**). Other hierarchies also change
under complete-top mapping: the unchanged wrapper grows by 11,062.1280,
while other logic/cell sizing supplies the remaining net reduction. The full
30,551 saving cannot be attributed solely to Page Manager's hierarchy, nor
predicted by adding isolated-component percentages. The wrapper remains
71.4% of this mapped control area and is still the dominant cost.

## Setup, hold and structural disposition

| Metric | RD1 | RD1+PM1 |
|---|---:|---:|
| Setup WNS | -0.36 ns | **-0.44 ns** |
| Setup TNS | -9,774.02 ns | **-12,096.60 ns** |
| Setup violating paths | 35,959 | **35,976** |
| Hold TNS / violating paths | 0 / 0 | 0 / 0 |
| Whole-report lint Warning lines | 44,536 | 44,541 |

Setup worsens by 0.08 ns, absolute TNS increases 2,322.58 ns (**23.762792%**),
and violating paths increase 17. The new worst reported path starts at
`directAssociationMaterializer/association_key_pending_descriptor_ref_reg[2]`
and ends at `io_functional_sidecar_read_issue_in_ready`. A critical path
outside the edited child does not localize the entire regression's cause;
whole-top mapping changed and needs a separately scoped timing diagnosis.

The report_qor WNS/TNS fields use nonnegative violation magnitudes. The JSON
retains these native values separately and normalizes signed WNS/TNS only
when violating paths exist, crosschecking WNS against `slack (VIOLATED)`.
Native timing reports have the original two-decimal precision. Hold's worst
reported slack is +0.01 ns with zero reported violations; this does not
retroactively clear PM1's different isolated-context hold result or establish
physical/multicorner timing safety.

The clock alias remains **577,110 loads**; the other high-fanout alias is
3,068 versus 3,071 loads. TIM-134 remains. Postcompile check_timing reports
no missing-delay/unconstrained-endpoint diagnostic, but structural cleanliness
is open: unused ports, feedthrough, shorted/constant outputs remain, and
native constraint reports retain min-capacitance violations. No LINT-3 or
LINT-5 occurs in Route-A. This is not a lint or clock-load improvement.

The appropriate result is **small measured area benefit with a worse setup
tradeoff**, not an unqualified improvement. Keep this as a complete measured
candidate; do not launch a replacement or relax the clock to hide timing.
The accepted WCG1 15.624812% isolated-wrapper saving remains separate and
cannot be subtracted arithmetically from this full-top area. Any later
cumulative full paired DC requires its own frozen input and native checks.
Arrays/external services remain nonzero/unestimated. PPA, external-service
zero cost, system speedup and hardware net benefit are not established.
