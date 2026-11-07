# RD1+PM1 setup regression — diagnosis in progress

Authorization: locate the setup regression, decide whether to repair it, then
choose a WCG1 full-paired integration route. Do not start another synthesis
or change functional/handshake semantics while diagnosing the cause.

## Existing native evidence

Both accepted full runs retain identical fair-v1 numerics, library, clock
policy, Full-KV and entry_id preservation. Only the Page Manager source
changes. This establishes a controlled source comparison, not a guarantee
that other hierarchies will map identically.

The complete-top result is area -0.901596%, setup WNS -0.36 -> -0.44 ns,
TNS -9,774.02 -> -12,096.60 ns and violating paths 35,959 -> 35,976.
All source/hash/area evidence remains in
[`dc_rd1_pm1_full_paired_result_20261107.md`](dc_rd1_pm1_full_paired_result_20261107.md).

The saved native top-20 setup reports establish **two affected path families**:

1. Existing cross-owner ready/request chains remain critical. RD1 includes
   arbiter -> coreMemory -> readIngress -> packedReadIngress ->
   packedSidecarIssue at -0.36 ns. RD1+PM1 reaches the same sidecar-ready
   output at -0.44 ns, with a changed launch register and mapping. A separate
   M2/P3 -> delivery -> registry -> allocationMux chain similarly appears at
   -0.36 and -0.44 ns. Neither listed path traverses Page Manager. This is
   evidence of remapping outside the changed child, not proof of stochastic
   tool noise or permission to alter R2 arbitration.
2. Six of the new top-20 paths directly traverse Page Manager's
   `allocatedLine_12609_reg -> reclaimLine_reg[0..5]`, all printed at
   -0.44 ns. None of the old top-20 paths is Page-Manager-local. The candidate
   path explicitly includes `nextAllocatedLine_selectedWide[3]`, connecting
   it to PM1's changed selector. Thus a purely external-remapping explanation
   is insufficient. Top-20 absence does not establish the old selector slack.

PM1 changes only the same-cycle exact-lowest reclaim selector: 36,720 bits
are split into 574 banks of 64, then bank priority and dynamic bank-offset
selection are composed. State, empty-input convention, lowest-index ordering
and capture edge remain unchanged. Bank priority/offset selection is a
concrete timing suspect; the exact failing subnetwork and its contribution
must be measured before choosing a replacement tree. No evidence currently
supports a new pipeline stage, register deletion or changed ready timing.

## Saved-DDC diagnostic successor

Use two independent native processes sequentially in a private tmux/workspace.
Read only the accepted mapped RD1 and RD1+PM1 DDCs; verify their exact hashes,
link the same DB and preserve their saved 2-ns ideal-clock constraints. Do not
compile, characterize, change timing exceptions, apply a clock/hold repair or
rewrite either DDC. New files are diagnostic reports only.

The prepared Tcl emits six-digit setup reports for all 16 reclaimLine D pins
and four common external endpoints, plus top-20, QoR, area, clocks and timing
coverage. It enumerates up to 100,000 negative-slack paths with one worst path
per endpoint/group, recording endpoints, starts and slack. Partition these
into Page-Manager endpoints and other endpoints. Compare count and summed
slack with native QoR before interpreting this as complete TNS coverage;
different counting conventions must remain explicit. An endpoint partition
is not a claim that every path to that endpoint stays within its hierarchy.

The native job uses unlimited stack, nice 10, at most two DC cores, at least
16 GiB available and a new immutable output root. Required completion is
both native exits/markers, clean native/redirected error scans, unchanged
DDC/library/Tcl hashes and outer persisted exit 0. Tool/artifact PASS alone
does not establish the regression's cause or close timing.

Local shell syntax/CLI help, Tcl completeness and no-mutation scope checks
pass. These preparation checks are not native execution results. The
machine-readable launch record freezes paths, hashes and observed startup.

## Decision gates before WCG1 integration

The preliminary evidence warrants investigating PM1 repair before treating
RD1+PM1 as the default next baseline. A 0.90% area benefit is insufficient
to dismiss a direct selector timing failure. However, replacing that selector
alone cannot be assumed to fix the independent cross-owner critical chains.

After the native diagnostic, decide between a same-cycle equivalent PM1
selector repair with local/full-child verification, or preserving PM1 as a
measured area/timing tradeoff and using accepted RD1 as the clean attribution
baseline for WCG1. Do not mix an unverified PM1 repair into WCG1's next input.
No final choice or RTL repair is made by this preparation record.

Any future WCG1 full-top input must retain all 366,336 data bits, 4,608 native
gates with TE=0, both 64-bit fields, all readers/enables/handshakes, five array
proxies and 48 entry_id drivers. Raw original-policy results and matched
propagated-clock/hold-pass supplements must be distinguished. If the latter
is applied, apply it to both complete tops and report separate results; do
not compare a new clock policy against the old 145.424x/146.747x runs as a
pure RTL change. Keep 2 ns and all numerical constraints unchanged. RD2 stays
excluded. A full run needs a new frozen closure and separate launch; none
is authorized or launched merely by starting this read-only diagnosis.

No PPA, service-zero-cost, speedup or net hardware-benefit claim follows.
