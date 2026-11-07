# RD1+PM1 saved-DDC setup diagnosis — accepted r2 result

`rd1_pm1_setup_diagnosis_20261107_r2` completes successfully. Both native
exits, native PASS markers, outer RUN_PASS and persisted outer exit 0 agree.
The RD1 and RD1+PM1 DDCs, target DB and frozen Tcl rehash correctly; the
versioned runner/Tcl match the launch pins. Native logs and redirected
reports contain no Error/Fatal. Both saved clocks remain ideal at 2 ns;
no constraint is changed, compile invoked or source DDC rewritten.
The named r2 tmux is idle bash. Original failed r1 remains preserved.

Source/launch authority:
[`dc_rd1_pm1_setup_diagnosis_retry_20261107.md`](dc_rd1_pm1_setup_diagnosis_retry_20261107.md).
Independent metrics and artifact hashes:
[`dc_rd1_pm1_setup_diagnosis_result_20261107.json`](dc_rd1_pm1_setup_diagnosis_result_20261107.json).

## Complete negative-endpoint coverage

The endpoint dump contains one unique negative-slack endpoint per row.
Counts exactly reproduce native QoR: 35,959 for RD1, 35,976 for RD1+PM1.
Summed nine-decimal endpoint slacks reproduce native two-decimal TNS within
rounding. Thus this run closes the coverage question raised in preparation.

| Endpoint partition | RD1 count | RD1+PM1 count | RD1 TNS (ns) | RD1+PM1 TNS (ns) |
|---|---:|---:|---:|---:|
| Page Manager | 597 | 615 | -125.402705 | -221.090725 |
| All other endpoints | 35,362 | 35,361 | -9,648.616007 | -11,875.506768 |
| Total | 35,959 | 35,976 | -9,774.018711 | -12,096.597493 |

Total absolute TNS worsens by **2,322.578782 ns**. The Page Manager endpoint
partition contributes **95.688021 ns (4.119904%)**; the other endpoint
partition contributes **2,226.890762 ns (95.880096%)**. These are endpoint
accounting shares, not a proof that 95.88% is causally independent of PM1.
An endpoint's owner does not identify every owner traversed by its path.

The major non-PM endpoint TNS increases are registry 592.933725 ns,
M2 control 512.111669 ns, arbiter 510.160662 ns, delivery 278.310537 ns and
M2/P3 245.731080 ns. The negative-path count outside PM actually decreases
by one while its TNS increases: many existing failing endpoints get worse,
instead of the total being driven by a large number of newly failing paths.

## PM1: a real local selector regression

Native STA compares all 16 identical `pageManager/reclaimLine_reg[*]/D`
endpoints in both DDCs. The original selector already fails 12 of them;
PM1 fails all 16. The worst bit is bit 3 in both designs.

| Metric for worst reclaim-bit path | RD1 | RD1+PM1 |
|---|---:|---:|
| Launch | allocatedLine_29680 | allocatedLine_12609 |
| Capture | reclaimLine[3] | reclaimLine[3] |
| Arrival time | 2.236238 ns | 2.333142 ns |
| Required time | 1.887306 ns | 1.893885 ns |
| Slack | **-0.348932 ns** | **-0.439257 ns** |
| Positive-delay combinational cell output arcs | 107 | 147 |

The output-arc count includes buffers and is a mapped-path observation,
not an abstract logic-depth specification. Arrival worsens 96.904 ps; the
capture requirement improves 6.579 ps, leaving a **90.325-ps slack loss**.
Launch clock-to-output delay changes 44.618 -> 55.381 ps, and the remaining
combinational arrival interval changes 2.191620 -> 2.277761 ns (+86.141 ps).
The launch mapping changes DFQD2/Q to DFD1/QN; the saved-clock budget is
unchanged. This is not an uncertainty/clock-setting artifact.

The implementation first computes 574 bank-valid values and local 6-bit
offsets, priority-encodes the winning bank, then uses that encoded bank to
select one of 574 local offsets. The six low output bits traverse this
offset-selection structure; their PM1 slacks cluster at -0.438167 to
-0.439257 ns. Bank-number bits 6..15 are less critical but all are negative.
The prior full report also retains the selectedWide[3] intermediate net.

Banking has reduced area without producing a shallow balanced selection
network. The implementation's bank-priority -> indexed offset selection,
plus its chosen cells/buffers, is a confirmed local timing bottleneck.
STA does not separately label every delay as bank-encoder versus mux delay,
so do not fabricate that finer split. This does justify repairing the
selector before accepting PM1 into the next cumulative baseline.

## Other control paths: existing combinational chains remapped

Common endpoint comparisons use identical port names and the same saved
constraints. Worst launch registers can differ; these are endpoint-family
comparisons, not an assertion that individual paths are identical.

| Common endpoint | RD1 slack (ns) | RD1+PM1 slack (ns) | Change (ps) |
|---|---:|---:|---:|
| Sidecar read issue ready | -0.362470 | -0.439984 | -77.514 |
| Sidecar registry allocate ready | -0.362409 | -0.439728 | -77.319 |
| External core-memory request valid | -0.362484 | -0.417399 | -54.915 |
| Registry allocation ack valid | -0.100951 | -0.100960 | -0.009 |

The sidecar-ready critical path traverses arbiter -> coreMemory -> arbiter
-> readIngress -> packedReadIngress -> packedSidecarIssue. It does not enter
Page Manager. Its arrival changes 2.062470 -> 2.139984 ns with the same
1.700000-ns required time. The path prefix through launch/arbiter reaches
1.795992 -> 1.860534 ns; the coreMemory interval is 0.192515 -> 0.209669 ns.
The worst source moves from an arbiter outstanding-incarnation register to
a direct-association pending-descriptor reference register feeding arbiter
matching logic. These are long existing identity/eligibility/request and
combinational ready chains, with changed mapped launch/cone/cell choices.

The allocate-ready path traverses M2/P3 -> packReadIssue -> delivery ->
registry -> delivery -> allocationMux, also without Page Manager. Arrival
changes 2.062409 -> 2.139728 ns with the same 1.700000-ns requirement.
The M2/P3 portion reaches 1.317408 -> 1.379468 ns, accounting for 62.060 ps
of this sampled path-family difference. The ack-valid endpoint barely
changes, so this is not a uniform 80-ps change in timing constraints.

All 47 non-PM input compilation units were byte-identical in the accepted
full-run audit. The observed external regression therefore resides in the
complete-top mapping of unchanged RTL, rather than a newly added PM logic
stage in these sampled paths. Area/sizing redistribution is consistent with
the cell/hierarchy changes, but the exact DC optimization heuristic or
run-to-run sensitivity has not been isolated by a controlled mapping replay.
Do not label it proven randomness, or claim that removing PM1 guarantees a
future compile reproduces every old slack. Do not reopen R2 arbitration or
insert handshake latency as a shortcut.

## Repair and WCG1 baseline decision

**PM1 requires a same-cycle selector improvement before cumulative
integration. It need not block WCG1's independent full-top validation.**
Retain PM1 as a measured 0.901596% whole-top area benefit with a setup
regression, not as the default next implementation. A suitable repair
candidate propagates `{valid,index}` through a balanced exact-lowest tree,
avoiding bank-index encoding followed by a wide indexed offset selection.
Preserve all state, empty-input terminal index, lowest-index ordering, final
partial bank, capture edge, reset and external handshake behavior. This
is a proposal, not RTL or measured improvement.

Before any repaired PM1 integration, require exact-selector equivalence
(including empty/full, boundary and final-partial-bank cases), real Page
Manager reclaim tests and matched native child setup/hold/area evidence.
The timing goal is nonnegative 2-ns selector slack; recovering old RD1 slack
alone is non-regression evidence, not timing closure. A PM1 repair cannot
be assumed to resolve the much larger non-PM endpoint TNS population.

The next WCG1 complete paired-DC baseline is **accepted RD1**
(`dc_feasibility_fair_rd1_shared_20261105_r1`): entry_id repair + compact
membership + RD1 sharing, **PM1 off and RD2 excluded**. Keep this next run
separate from PM1 repair and any ready-chain optimization. RD1 itself is
setup-failing; it is a controlled attribution baseline, not timing-closed.
The full freeze/STA acceptance policy is in
[`dc_wcg1_full_paired_integration_baseline_20261107.md`](dc_wcg1_full_paired_integration_baseline_20261107.md).

This audit changes no RTL and launches no tool. It accepts diagnostic
tool/input/endpoint coverage and the integration decision; it does not close
setup, structural cleanliness, PPA or system net benefit. Local clock-report
regressions and result/coverage consistency checks plus `git diff --check`
must pass before the separate documentation commit.
