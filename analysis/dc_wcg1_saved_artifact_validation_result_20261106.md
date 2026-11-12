# WCG1 saved-artifact validation: accepted matched-bank screen

Disposition: **ACCEPTED_MATCHED_BANK_SCREEN**.
Validation ID: `wcg1_saved_artifact_validation_20261106_r1`.
Native source run: `wcg1_bank_mapping_sta_20261106_r1`.
Repaired tooling commit: `bbc90347405f9b5b72d46796180df38099896ebd`.
Evidence and exact checksums:
[`dc_wcg1_saved_artifact_validation_result_20261106.json`](dc_wcg1_saved_artifact_validation_result_20261106.json).

This closes the summary failure diagnosed in
`H4对应研究过程`. It accepts the existing
one-bank mapped-area and cell-clock STA screen, after its planned hold
repair. It does not integrate clock gating into the generic production
wrapper. No DC/EDA executable was invoked; no analyze, elaborate, compile,
DDC reload, RTL modification or RD2 access occurred.

## Tool/input/artifact closure: PASS

The new independent validation in `kvzap-wcg1-map:saved-check` completes:

```text
KVZAP_WCG1_MAPPING_POSTCHECK_PASS
KVZAP_WCG1_SAVED_VALIDATION_RUN_PASS
KVZAP_WCG1_SAVED_VALIDATION_OUTER_EXIT=0
```

Both source native sides still have exit 0 and their executed side/stage PASS
markers. Original r1 **outer exit remains 1**. The new receipt supersedes
the failed summary for acceptance; it does not rewrite historical success.

Original archive SHA-256 remains
`afb10d4cf6f0c1c801c1c87c684b6a30c3767abb0a92ff9200a3429300ea7990`;
actual DB remains
`5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.
All frozen inputs, manifest, launch/diagnosis records and report/HDL/DDC pins
pass before and after validation. All 78 files in the original result tree
retain identical content hashes; the fetched copies agree with that complete
inventory. Four DDC and mapped HDL/SDC snapshots remain intact.

Validator archive SHA-256:
`2a4ec711988c6d2579e60c33a614ec37d9f74e9375f7535fb779f40d1b1c961e`.
Accepted result.json SHA-256:
`fc5f02d45844ab3e9216e67edab29cd9b0562a15eb6aec7606657282d4839ee8`.
Validator, receipt and result hashes are in the linked JSON.

The repaired summary reads native **Total cell area**, requires finite,
positive, unique values, and cross-checks combinational/sequential components
and QoR. Precision timing reports supply slack, cross-checked with original
scalar metrics. r1 empty-area recovery is explicitly enabled only with pinned
provenance and its known UID-101 signature. Source metrics are untouched.
The future Tcl area reader is corrected and tested with ordinary Tcl, not
executed in DC. All 26 focused regressions pass.

Remote result directory:
`/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/wcg1_saved_artifact_validation_20261106_r1/`.
The separate sibling `wcg1_saved_artifact_validation_20261106_r1_receipt/`
contains launcher.log, exit_status and result_sha256.txt. Original mapping
reports remain in the original r1 root. No new synthesis run exists.

## Mapped-area improvement: PASS within the matched bank

| Snapshot | Reference cell area | Gated cell area | Reduction |
| --- | ---: | ---: | ---: |
| raw | 56,919.576720 | 47,433.287347 | 16.6661% |
| hold repaired, accepted | 56,919.576720 | 47,512.919348 | **16.5262%** |

Accepted absolute savings are 9,406.657372. Gated hold repair adds 79.632001
area, which is included in the accepted comparison. Repaired reference
sequential/combinational areas are 36,662.137178 / 20,257.439542; gated areas
are 26,727.287798 / 20,785.631550. Smaller sequential cells outweigh the
additional gates, buffers and repair cost in this isolation fixture.

The bank still stores all 10,176 bits. This is a storage-cell realization
improvement, not compression of the two opaque 64-bit fields or reduced
functional capacity. The four member and two suffix read interfaces and
common registered launch/mask boundary remain as frozen for this screen.

## Timing closure: PASS at 2 ns in this screen

All four saved SDCs pass the identical numerical profile: 2-ns clock,
0.10/0.02-ns setup/hold uncertainty, 0.20-ns input/output delays, 0.05-ns
transitions and 0.005 output loads. Reset remains timed, clocks propagate
actual cell arcs, and no false/multicycle path is introduced.

| Repaired precision metric | Reference | Gated |
| --- | ---: | ---: |
| Worst setup slack | +1.064047 ns | +1.064047 ns |
| Worst hold slack | +0.040393 ns | +0.003529 ns |
| Setup / hold violating paths | 0 / 0 | 0 / 0 |
| Setup / hold TNS | 0 / 0 | 0 / 0 |

Gated enable worst setup/hold slack is +1.649341 / +0.066130 ns. Its actual
capture paths include nonzero CKLNQ increments and downstream clock buffers.
The checker tests the increment column, not just a nonzero transition.
Both repaired native constraint reports state no violated constraints.

The raw gated design failed hold: worst -0.017921 ns, 9,992 violating paths,
rounded TNS -68.32 ns. That negative result remains in the accepted record;
only the repaired snapshot closes timing. Setup slack is unchanged. The
3.529-ps repaired hold margin is small: this single slow-corner, wire-load
screen does not establish physical/multicorner hold signoff or CTS behavior.

## Structural cleanliness: preserved, not zero lint

Mapped HDL inventories independently retain all 64 x (79+80) data bits on
both sides, EDFQD enabled flops in reference and DFQD plus 128 CKLNQ gates
in candidate. No GTECH/SEQGEN instance remains. DDC, mapped HDL/SDC, QoR,
hierarchical area, timing, clock and constraint reports all pass the artifact
gates, with no native Error/Fatal or timing-coverage warning.

Each side/stage retains the same 12 LINT-28 warnings from unused ports of
two DesignWare equality comparators. These are recorded and do not represent
new data-driver loss; the screen is not lint-free. The manual gate inventory
and native gate timing checks remain authority even though Power Compiler's
insertion report does not inventory the explicitly instantiated gates.

## Non-conclusions

The accepted 16.5262% is for one matched bank, including its common isolation
shell and read networks. It is not whole-wrapper/Route-A area reduction;
do not multiply it by 36 or update the existing full paired-DC area ratio.
Generic-wrapper integration/equivalence and full-top timing/area remain open.
No PPA, physical signoff, external-service zero cost, system speedup or
hardware net-benefit claim follows from this acceptance.
