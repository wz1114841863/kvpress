# RD2 isolated read-network result: valid run, no area benefit

Run: `rd2_read_network_screen_20261106_r1`.
Disposition: **tool/input/artifact closure PASS; current decoded candidate
does not pass the mapped-area improvement gate**. Preserve it as a negative
screen, not an integrated optimization.
Evidence: [`dc_rd2_read_screen_result_20261106.json`](dc_rd2_read_screen_result_20261106.json).
Input contract: `dc_rd2_read_screen_input_freeze_20261106.md`.

## Tool/input closure

The remote run in `kvzap-control-refine:p27-rd2-read-dc` has ended. Both
native side PASS markers and exit-zero markers, postcheck PASS, total PASS
and `KVZAP_RD2_P27_READ_SCREEN_EXIT=0` independently recheck. Its pane is at
the shell. No restart, new synthesis, DDC load or RTL change was performed
for this inspection.

All 15 frozen input/source/script/provenance files rehash against the run
manifest; the nine separately recorded preflight pins also match. Both
emitted SVs match accepted p26 hashes and have identical normalized port
headers. Five copied Scala sources match the accepted test input manifest.
The native test XML still has two cases and zero failures/errors/skips,
covering 4 x 8 and 36 x 64 in-range differential tests. Actual p26 source
archive SHA-256 rechecks to
`582c87b96a4ae68e687e94f059cf5fd95404bd76739e5768733eb51b3ee6a8d0`.
Actual library DB SHA-256 is still
`5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.

Each side has non-empty native DDC, mapped HDL, area hierarchy, QoR,
precision setup/hold, clock, constraints, design/timing checks, resources
and the exact zero-register scalar summary. All native logs **and redirected
reports** are free of native Error/Fatal. The linked JSON records remote
DDC/mapped-HDL/report hashes; fetched reports match those hashes. The native
files remain in the original immutable root:

`/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/rd2_read_network_screen_20261106_r1/`.

The original total log is:
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/rd2_read_screen_p27_dc_20261106.log`.

## Mapped-area improvement: FAIL for this candidate

Both sides retain RD1's M/S/O shared reader and the same full 36 x 64
member/suffix input image. RD2 changes the remaining C/F/B member and M/C
suffix reader realization. All raw reads stay observable with valid low.
Storage is outside both tops, so every mapped cell is combinational.

| Native metric | RD1-enabled baseline | RD2 decoded candidate | Candidate change |
| --- | ---: | ---: | ---: |
| Total cell area | 689,972.294920 | 692,068.096534 | **+2,095.801614 (+0.30375%)** |
| Buffer/inverter area | 63,545.161020 | 125,808.648317 | +62,263.487297 |
| Other combinational area | 626,427.133900 | 566,259.448217 | -60,167.685683 |
| Sequential area / registers | 0 / 0 | 0 / 0 | unchanged |
| Cell count | 841,776 | 942,357 | +100,581 |
| Buffer count | 125,945 | 135,113 | +9,168 |
| Inverter count | 205 | 171,761 | +171,556 |

Native area and QoR agree. Use **Total cell area**, not the separate Total
area which is undefined under ZeroWireload. The decoded logic reduces the
area excluding buffers/inverters, but its added buffer/inverter cost exceeds
that saving. There is no measured incremental area benefit over RD1.

This is a small observed regression at one mapping point, not a claim that
all decoded-reader implementations or all integrated mappings are worse.
It nevertheless supplies no positive evidence to justify taking this exact
candidate into expensive production integration/full DC.

## Concrete structural explanation and fanout evidence

The read-only mapped-HDL auditor
`tools/audit_rd2_mapped_cells.py` streams the two existing netlists. Its
native-cell counts match both native reports exactly, including all buffers
and inverters. Candidate inverter inputs include:

- 73,728 connections directly to member-table input bits;
- 92,160 directly to suffix-table input bits;
- 5,825 to internal nets and 48 to other inputs.

The baseline has no direct member/suffix input inverters in this inventory.
Thus most added inverter instances implement data-input polarity, rather
than new state or only high-fanout buffer repair. The decoded AOI/OAI mapping
creates a large per-bit polarity cost at this combinational input boundary.
Attributing that cost to the candidate's Boolean realization is supported
by the source change and native structure; individual cone area is not
independently characterized.

For example, baseline maps 364,510 AOI22D0 cells while candidate maps 94,782;
candidate instead includes 202,752 AOI221D1 and 206,976 OAI22D1 cells, together
with the 171,761 INVD1 cells. Shorter source code/explicit shared decode does
not guarantee a smaller mapped network in this library.

Syntactic input-pin fanout maxima are 81 and 100, respectively, involving
the common valid feedthrough nets; mapped bank-related AND outputs reach 79
in both inventories. These counts exclude output loads and continuous-assign
alias resolution and are **not** native STA fanout or physical routing
measurements. No TIM-134 warning occurs in either native log; both QoRs
report zero max-transition/max-capacitance violations. The measurements do
not support diagnosing this result solely as uncontrolled fanout growth.

## Timing: isolated 2-ns I/O gate passes, no timing improvement

Both use unchanged fair-v1 numerical values: period 2 ns, setup/hold
uncertainty 0.10/0.02 ns, input/output delays 0.20 ns, transition 0.05 ns,
output load 0.005. The copied constraint script hash is unchanged.

| Native precision metric | RD1-enabled baseline | RD2 decoded candidate |
| --- | ---: | ---: |
| Worst setup slack | +1.046292 ns | +1.026872 ns |
| Worst reported path logic delay, excluding 0.20-ns input delay | 0.453708 ns | 0.473128 ns |
| Worst hold slack | +0.380000 ns | +0.380000 ns |
| Setup / hold TNS | 0 / 0 | 0 / 0 |
| Setup / hold violating paths | 0 / 0 | 0 / 0 |
| QoR logic levels | 22 | 24 |

The overall worst logic path is 19.42 ps longer in the candidate. However,
both 20-path setup reports end at `io_payload_0[...]`, part of the common
RD1 M/S/O reader. The first baseline path starts at `io_valid_0`; candidate
starts at `io_layer_0[4]`. These reports therefore do **not** establish that
each modified C/F/B/M-suffix reader individually became slower. Common
logic can map differently when the surrounding Boolean network changes.

Both tops have zero registers. Clock/reset are unused harness ports; the
clock is the ideal I/O timing reference. The minimum hold path is the valid
feedthrough, with its margin supplied by the declared I/O delays. Passing
these checks is not evidence of integrated register-to-register hold,
gated-clock closure, full Route-A timing closure, CTS or physical signoff.

## Structural cleanliness and functional boundary

Both sides have exactly the same 34 native lint warnings:

- 2 LINT-28: clock/reset unused in the combinational harness;
- 3 LINT-29: valid input-to-output feedthroughs;
- 14 LINT-31 and 15 LINT-52: the intentionally zero materializer position
  bus shares the constant node across its bits.

These match the emitter's documented conventions; no LINT-3/LINT-5 appears,
and the native timing check reports no unconstrained-endpoint warning.
No register or macro/black-box was introduced. This is matched residual
lint, not zero lint or evidence of production `entry_id` driver behavior.

Functional evidence remains the accepted two-case **in-range** source miter,
not a new formal postmapped-equivalence proof. Out-of-range layer behavior
and complete continuous-ready semantics remain an explicit production gate.
Nothing in this successful tool run closes that outstanding contract scope.

## Disposition and non-conclusions

Keep current production RD1 unchanged and preserve the RD2 source, inputs and
negative result. Do not integrate this exact RD2 candidate as an accepted
area optimization or launch a full paired DC on its behalf. The result
does not reopen admission, pruning, publication, authority or arbitration.
It does not invalidate the independent WCG1 matched-bank positive screen.

No full Route-A/Full-KV area ratio is updated, and RD1/PM1/WCG1 savings may
not be added arithmetically to this isolated network. No PPA, external-service
zero cost, system speedup or hardware net benefit is established. This batch
only inspects existing results and records the failed optimization gate.
