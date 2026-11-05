# RD1 full paired-DC result — 2026-11-06

## Disposition

`dc_feasibility_fair_rd1_shared_20261105_r1` completes with both native exits
zero, `KVZAP_DC_FEASIBILITY_RUN_PASS`, and `KVZAP_RD1_P16_DC_EXIT=0`.
The RD1 processes have exited.  Its old pane is absent; completion is
established from the persisted log and reports, not window visibility.

Tool/input closure and mapped-area improvement pass.  Setup timing and broad
structural cleanliness remain blocked.  This run contains RD1 plus accepted
compact membership and entry-id repair; it does not contain PM1 or RD2.

## Fair input closure

The unchanged `dc_feasibility_fair_v1` numerical profile and constraint Tcl
were compared directly with immutable baseline
`dc_feasibility_fair_r5desc_20261029_r1`: 2.0-ns period, setup/hold uncertainty
0.10/0.02 ns, input/output delay 0.20 ns, input transition 0.05 ns and output
load 0.005 pF.  Both manifests and 1/48 compilation-unit lists are present.
All required native reports, DDCs and mapped HDL are non-empty.

The five entries in `input_sha256.txt` independently recheck:

- target library: `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`;
- paired archive: `9494f1dc4b47f1bfbcffe655b75e20a0d4c9cd75fb9802b5d454f870ae02dc5b`;
- entry-id preservation Tcl: `a936bd9453002fc3de7f7388aa78c3e74cf31e45a0461773105935ae0157438d`;
- proxy materialization: `9a63d4dc35d6a83157bb6eb39a3c440e3af07fd4d5f74be7122d1385fe00acbf`;
- proxy check: `6f2b2389bcbcc95d7bf77fb1da9bb0f040a7ca6331f73ea35e44bfa82d951bc2`.

Copied proxy manifest SHA-256 is
`9a54405e9c2a91ae51bc2b298bf8c40bd86177f87f02f1d72ae3bf59cda341b0`;
constraint Tcl SHA-256 is
`3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007`.
The five proxy-instance reports retain exactly one of each approved boundary.

Full-KV reproduces all parsed QoR metrics exactly against both immutable
baseline and accepted entry-id predecessor.  Its area is 23,091.432498,
sequential cells 5,060, setup/hold TNS and violating-path counts zero.  Its
one VER-41 missing Verification include is identical to both predecessors;
it is a retained baseline diagnostic, not a new RD1 error.  Route-A has no
native Error/Fatal line.

## Mapped area and state

| metric | accepted compact/entry-id | RD1 | change |
|---|---:|---:|---:|
| total cell area | 3,622,375.558791 | 3,388,597.345862 | -233,778.212929 (-6.454%) |
| combinational area | 1,640,278.407905 | 1,392,283.363726 | -247,995.044179 (-15.119%) |
| noncombinational area | 1,982,097.150886 | 1,996,313.982136 | +14,216.831250 (+0.717%) |
| leaf cells | 2,926,574 | 2,540,638 | -385,936 |
| combinational cells | 2,349,468 | 1,963,532 | -385,936 |
| sequential cells | 577,106 | 577,106 | 0 |
| area / Full-KV | 156.871x | 146.747x | -10.124 ratio points |

Hierarchy localization:

| hierarchy | accepted compact/entry-id | RD1 |
|---|---:|---:|
| M2/P3 wrapper | 2,638,229.5377 | 2,387,543.1337 |
| Page Manager | 407,451.2386 | 407,306.5906 |
| M2 production control | 175,682.9790 | 175,735.2263 |
| metadata bridge | 85,833.0491 | 85,833.3851 |

The wrapper reduction is 250,686.4040 (-9.502%), localized as intended;
its share falls from 72.8% to 70.5%.  Other hierarchy/cell-size changes reflect
whole-top mapping rather than new optimizations.  Relative to immutable
baseline total area 6,716,537.642416, the cumulative reduction is 49.548%.
RD1's incremental benefit is the 6.454% above, not that cumulative figure or
the isolated reader's 62.943% result.

## Timing and fanout

| metric | accepted compact/entry-id | RD1 |
|---|---:|---:|
| setup WNS | -0.31 ns | -0.36 ns |
| setup TNS | -8,577.41 ns | -9,774.02 ns |
| setup violating paths | 35,897 | 35,959 |
| hold TNS / violating paths | 0 / 0 | 0 / 0 |

Absolute setup TNS worsens by 1,196.61 ns (+13.951%); violating paths increase
62.  Worst reported setup path starts at an arbiter outstanding transaction
incarnation register and ends at the external core-memory request-valid
output.  Setup remains worse than immutable baseline (-0.31 ns,
-7,318.06 ns, 34,814 violating paths).

No new unconstrained-endpoint or design-rule-violation diagnostic appears.
The two high-fanout nets remain: the clock-alias net has 577,110 loads,
unchanged from the predecessor; the eligibility/control alias has 3,071 loads
versus 3,072.  RD1 reduces combinational logic, not state or clock load.

## Structural cleanliness

Entry-id validation reports `checked_bits=48 undriven_bits=0` and native
`KVZAP_R3_ENTRY_ID_DRIVER_PASS bits=48`.  LINT-3/LINT-5 remain zero.

Warning lines increase from 44,533 to 44,536.  LINT-31 increases four and
LINT-33 decreases one; all other category counts are unchanged.  The remaining
large unused-pin/net, feedthrough and constant-output populations prevent
broad cleanliness closure.  Do not describe this as a lint improvement.

## Artifact identities and conclusion

- Full-KV DDC: `88336cd0fd5e3835b60585dff31578aa8945a55b05707cd4ded3e5ef9f177dcd`;
- Full-KV mapped HDL: `e2e1258cda1cd1a1c4dc2e43c1b888a2ffc3cc7b15a8a02bf365e393a7966dfd`;
- Route-A DDC: `86993ae45bd58463ba4a18b67f12bc2fac864cd146004fd3c9a3c5a8481b5673`;
- Route-A mapped HDL: `d5471523b3a0e2ddc1ddf898f5563286c109869d6340ec549aef08068e9fdad8`.

RD1 is a confirmed complete-top area improvement with a measured setup timing
tradeoff and unchanged register/clock-load cost.  Its area benefit supports
retaining it as a candidate, while future integration must address the timing
regression rather than assume a fully favorable tradeoff.  This is logic-only
feasibility evidence, not PPA, physical timing, external-service zero cost,
system acceleration or hardware net benefit.  No new synthesis is launched
by this result inspection.
