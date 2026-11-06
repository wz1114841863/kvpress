# WCG1 matched bank mapping and gated-clock STA

Status: preparation verified; remote mapping not yet launched in this snapshot.
Authorization: user approved the matched isolation mapping and gated-clock STA
at the original 2 ns, using independent tmux and leaving RD2 untouched.
Predecessor: `dc_wcg1_cost_edge_feasibility_20261106.md`.

## Compared boundary and invariant

This screen maps one complete 64-record bank: 79-bit membership and 80-bit
pending-read suffix, 10,176 unreset data bits. It is an explicitly generated
isolation fixture, not an export or replacement of the production wrapper.
There are four independent asynchronous membership reads (shared M/S/O, C,
F, B) and two suffix reads (M, C). C/F consume the 64-bit reference subset;
M/S/O and B consume all 79 bits. A continuously observable C legality/ready
probe exercises presence/binding masks, ordinal range, reference/suffix
equality and stage/sink/valid inputs. It does not replicate the complete R3
admission join, publication state machine or cross-bank selection network.

Both sides contain the same 174-bit upstream registered launch boundary and
128 presence/binding bits. Only launch-fire and the masks are reset; data
storage retains its enabled-write behavior during reset. The common shell
adds no proposed production pipeline stage. It exposes root-launched data
and enables changing on the same edge that captures the old record, rather
than hiding internal hold risk behind an external 0.2-ns input delay.

Each membership write is a decoded accepted event for bank 3 and an exact
7-bit ordinal in [0,63]. Suffix writes additionally require binding-offered.
The raw bank does not add admission rejection or ordinal-nonreuse assumptions.
Reset/claim clears masks; it does not erase the two raw data tables.

| Side | Membership/suffix realization | Clock gates |
| --- | --- | --- |
| reference | 10,176 native EDFQD2 enabled flops | 0 |
| gated | 10,176 native DFQD2 flops | 128 native CKLNQD1 gates, separate 79/80-bit words |

Both storage architectures are size-only protected, allowing library drive
resizing while retaining the compared storage organization. Combinational
logic is normally mapped. No black boxes or automatic clock-gating transform
are introduced. This tests the proposed cell realization, not whether DC
would automatically choose it from the unchanged production Chisel.

## Matched timing and repair policy

Both sides source the unchanged `constraints_control_projection.tcl` and
frozen environment: period 2.0 ns; setup/hold uncertainty 0.10/0.02 ns;
input/output delay 0.20/0.20 ns; data transition 0.05 ns; output load 0.005.
Reset remains timed. No false paths or multicycle paths are added.

The matched supplement propagates the actual cell-clock arcs on **both**
sides and supplies the same 0.05-ns root-clock input transition. This is an
isolation STA policy, not a change to, or a repeat of, full fair paired DC.
No CTS, extracted wiring or external clock-tree insertion is modeled; native
wire-load assumptions are retained in each timing report. A single slow
library corner cannot establish physical hold signoff across corners.

Each side first runs `compile -map_effort medium`, saves raw mapped evidence,
then runs `set_fix_hold [all_clocks]` and `compile -only_hold_time`, saving
repaired evidence. Both use exactly the same repair policy. Area savings must
be reported before and after repair, alongside residual setup/hold and gate
enable checks. An unclosed design may still produce a complete experiment;
it must not be called timing-closed or an accepted implementation benefit.

## Gates and preparation evidence

- Library DB SHA-256:
  `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.
  Native functional model SHA-256:
  `4aac97c4efda0665cdc8af807a1f5f6706f69a2359453b244562cd8158f27cbf`.
- Generated reference and candidate pass native-cell functional simulation:
  all 64 rows initialized, scoreboard checks both tables, 768 concurrent
  output comparisons across bound/unbound writes, different banks, ordinal
  64 rejection, reset/claim, independent readers, valid-low ready and
  root-edge launch changes. This is unsdf unit evidence, not full-wrapper
  equivalence or timed gate-level simulation. The predecessor's high-phase
  edge/negative-control tests remain applicable and unchanged.
- Eight focused postcheck regressions pass, including redirected report
  errors, missing gate capture arcs, ideal-clock rejection and distinguishing
  negative hold slack from successful tool/artifact completion.
- Native preflight r1 detected an invalid DC-2018 pin-name filter before any
  mapping. Preserved unchanged. r2 uses explicit instance/pin glob queries,
  links all 10,176 flops/128 gates, verifies propagated-clock status, and
  reports real library clock-gating setup/hold checks. Its generic launch
  logic is unmapped: its slack is **not** a mapped timing result.
- DC `report_clock_gating` does not inventory these manually instantiated
  gates in the preflight. Gate counts therefore come from linked native
  cells, with independent E-pin checks, gating timing endpoints and actual
  positive CKLNQ Q arc increments required in mapped capture paths. A
  zero Power Compiler insertion count does not suppress STA checking.

Input archive/checksums, native logs, both side exits and outer marker must
all close. Each raw/repaired snapshot must contain DDC, mapped Verilog/SDC,
QoR, hierarchical area, reference counts, lint/timing checks, constraints,
full-clock setup/hold, clock reports and scalar metrics. Gated snapshots
add gate-enable max/min and root-launch-to-gated-data min paths. Scan all
redirected reports for native errors; console exit or a partial PASS is
insufficient. Preserve timing failures as results.

## Execution and disposition

Run reference then gated sequentially in a new immutable root, single DC
process at a time with `nice -n 10` and `ulimit -s unlimited`. Use the separate
`kvzap-wcg1-map` tmux session; do not query or manipulate RD2's windows,
processes, inputs or output trees. Generated RTL and vendor models remain in
ignored experiment/bundle directories. Commit only tooling and records.

No area reduction is claimed by this plan. No result may be multiplied by
36 and presented as integrated Route-A savings. Full generic-wrapper
equivalence, production integration, whole-top timing/area, PPA, service
costs, system speedup and hardware net benefit remain outside this screen.
