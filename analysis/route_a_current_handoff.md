# Route-A current handoff — RTL3 closure and measurement RTL status

**Status date:** 2026-11-09
**Repository state:** `research/kvzap-latest`; bounded RTL3 functional closure
and accepted control-mapping results remain preserved. RD1+WCG1 r2 completed
with tool/input/artifact closure and an 11.741151% primary top-area reduction
versus RD1 (129.517x Full-KV control). Global setup regresses and the matched
hold pass is not timing-closed. Complete costs and PPA/net benefit remain open.
Stage A default-v1 blocker probes remain preserved. The explicit default-off
persistent-read v2 r2 successor now has accepted bounded repeated-read,
error/recovery and retire-preflight evidence: 15/15 native tests, all five
exit layers zero, frozen input/artifact closure and strict final check PASS.
The R5 parent lookup-ownership repair is qualified in this scope; r1 failure
is retained. Multi-group admission/journal, full capacity/concurrency/numeric
and external-v2 functionality remain open. Original normative v1 contracts
are preserved; the v2 functional successor adds no new area/timing or net-benefit
evidence. The multi-group journal lifecycle audit now separates a 64-row working
set from cumulative exact history, and specifies safe migration/close barriers.
An acknowledged finite registration window is only a versioned contract
alternative, not an established release guarantee. Physical history service,
complete costs and 2ns closure remain open.

This is the compact, living entry point for a new discussion or implementation
turn. It summarizes current status; it does not replace frozen evidence,
historical review records, or the normative architecture contract.

## Multi-group journal lifecycle and minimal plan (2026-11-09)

Read [`route_a_multigroup_journal_lifecycle_closure_20261109.md`](route_a_multigroup_journal_lifecycle_closure_20261109.md)
and JSON. Source `1f752ee` confirms reset-only late lookup, a 64-row/2,264-B
working journal, and a separate one-registration-per-reset pending owner.
Publication, R6 handoff, S2 release and retire do not revoke old lookup rights.
The compatibility baseline remains exact-history migration plus two close ACKs
before separate rearm; cold keep-all history can reach 9,400,320 records.
The previous 32-B direct layout provisions 288 MiB, not a required minimum,
observed workload use, on-chip area or economical implementation acceptance.

Before RTL, qualify whether the producer can acknowledge registration closure
and owners can retain/drain every accepted consequence. Only an explicitly
versioned Closed/Expired contract could then bound history to one 64-row
window. No such guarantee exists today. Otherwise complete the exact-history
physical service/cost contract first. Repeated pending-owner recycling is a
separate obligation. This batch changes documentation only and starts no
RTL/native/remote/DC/STA work; Stage A multi-group functionality remains open.

## Persistent page read r2 bounded functional acceptance (2026-11-09)

Read [`route_a_persistent_page_read_r2_result_20261109.md`](route_a_persistent_page_read_r2_result_20261109.md)
and JSON. Source `40a74b6`, 155 inputs and archive hash match; fresh archived
final checker and an independent audit accept 7 suites/15 native tests,
unchanged parent snapshot, all XML/ELF/log artifacts, exact markers and
compile/parent/test/runner/tmux exits 0/0/0/0/0. Pane14445 is idle, no children.

One real packed write/publication supports two actual payload/sidecar fills,
eight consumer commits, two releases/terminals, fresh S2 generation1-to-2 and
final retire/reclaim. Four invalid attentions fault without extra service,
foreign declaration creates no terminal, and legal recovery passes. Retire
with an accepted attention/declaration but missing selector finishes the old
service before reclaim. Default-v1 4 functional and 2 expected-blocker tests
also pass. Scope is small internal-backing, one valid tail member, packed-only
sequential service, gate flag off and numeric=0. No full32K/mixed/external,
multi-group/journal, numeric, 2ns or complete-cost acceptance follows.

This inspection changes no RTL/input and starts no test/DC/STA. Stage A's
repeated-read witness is closed in the tested v2 envelope; Stage A as a whole
still awaits multi-group lifecycle/history and broader evidence.

## Persistent page read r2 launch snapshot after parent-gate PASS (2026-11-09)

Historical snapshot; completed acceptance is recorded above.

Read [`route_a_persistent_page_read_r2_launch_20261109.md`](route_a_persistent_page_read_r2_launch_20261109.md)
and JSON. Frozen source `40a74b6`, 155 files, archive SHA
`e7a65e92cf22c9c4ab620d3094c94c05b21b6874a8e5d8d053da3196e7a293ee`,
run `persistent_page_read_v2_20261109_r2` is in independent tmux
**`kvzap-persistent-read-v2-r2:validation`**. Actual input/remote compile and
real R5-parent native test pass, with strict XML/ELF/log/typed-marker snapshot.
The unchanged fourteen-test phase has now started; full15/outer closure is
pending. Parent PASS closes only this short regression, not repeated-read/
error/retire whole-DUT acceptance. User notified to wait; no DC/STA or retry.

## Persistent page read r2 repair prepared (2026-11-09)

Read [`route_a_persistent_page_read_r2_repair_20261109.md`](route_a_persistent_page_read_r2_repair_20261109.md)
and JSON. R5 now sets scanner outstanding only for its own scanAllowed fire;
v2 response asserts no phantom scanner work. R3/Admission/M2/R2/R6 and all
other 29 production main files match `67459cc`. Whole-DUT timeout reporting
adds actual read-only observations without widening the bound.

New real-R5 parent regression covers mark/query/query, actual scan overlap
and held responses. A separate r2 runner must pass and snapshot this one
native test before running the unchanged fourteen-test phase (15 total).
Local compile/lowering and 22 checker short tests pass; native results remain
pending. r1 flow/results stay preserved. External-backing service ownership
has a separate pre-existing OPEN issue, outside the internal-backing coverage.

## Persistent page read v2 r1 failure inspected (2026-11-09)

Read [`route_a_persistent_page_read_result_20261109.md`](route_a_persistent_page_read_result_20261109.md)
and JSON. Compile/test/runner/tmux exits are 0/1/1/1, 152 input hashes match,
and 14 native builds/reports are preserved. Five v2 owner units and six v1
tests pass; all three v2 whole-DUT cases time out at the first packed READY,
before second-read/error/retire branches. The archived strict checker rejects
the run correctly. Pane is idle with no descendant task; no automatic retry.

Saved protocol records are identical across the three failures: publication,
post-R6 receipt and page notice occur, but R5 positive grant never fires and
S2 remains Empty. Frozen source/native HDL show v2 mark lookup incorrectly
sets scanner scanOutstanding; its response bypasses scanner clearing, blocking
the next query. This register value is inferred from exact logic, not a direct
GET. Next repair should isolate scanner-owned request bookkeeping and first
test the real R5 parent mark-to-query path. No production RTL or input change,
new simulation/DC/STA, functional acceptance, area/timing or net-benefit claim.

## Persistent page read v2 remote validation launch snapshot (2026-11-09)

Historical launch state, superseded by the completed failure inspection above.

Read [`route_a_persistent_page_read_launch_20261109.md`](route_a_persistent_page_read_launch_20261109.md)
and JSON. Source `1d49fc8` is frozen in a new 152-file archive, SHA
`40973dc895eb4a72798aeb9da760efdac8d71a1f79614857f392ddacef7ab119`.
Independent tmux is **`kvzap-persistent-read-v2-r1:validation`**, run
`persistent_page_read_v2_20261109_r1` under the remote artifacts root.
Fresh input hashes pass, remote compile exit0/COMPILE_PASS and SIMULATION_BEGIN
are present. The first native Verilator build is observed; test/outer exits
and all 14-test functional acceptance remain pending. User notified to wait.
No DC/STA, multi-group change, old-job cleanup or automatic retry. Use the
archived checker with `--final` after completion, including tmux wrapper exit.

## Persistent page read v2 implementation prepared (2026-11-09)

Read [`route_a_persistent_page_read_preparation_20261109.md`](route_a_persistent_page_read_preparation_20261109.md)
and JSON before accepting the next functional successor. Explicit default-off
`persistentReadEnabled` adds R5 persistent qualification/query, R6-owned
preflight/reject/unplanned state, S2 typed reservation and an independent R3
receipt collector. R3/Admission/M2 and R2 protected regions are byte-identical
to `822c4c9`. Single-group journal/Done behavior remains; no archive or DC/STA.

Local Scala/Chisel/firtool and short checker gates precede a planned 14-test
independent remote native run. Preparation is not repeated-read acceptance.
Retire stops new frontend work first, then drains existing accepted service
before closing transport ingress. Scope remains the small functional fixture,
external position/partial/R4 reference and no numeric/full32K/mixed-top closure.
Consult a later launch/result record for actual run status, hashes and exits.

## Stage A minimal continuation proposal (2026-11-09)

Read [`route_a_continuation_minimal_proposal_20261109.md`](route_a_continuation_minimal_proposal_20261109.md)
and JSON. Candidate production-v2 adds R5-owned post-R6 read_ready and explicit
page selection/query; an attention-independent collector replaces repeated
consumption of publication facts. R6/S2 preflight authorization, typed negative
responses and exact reject/drain are required, rather than indefinite ready-low.
Generic/v1 behavior and all frozen arbitration/publication/authority remain.

Keep the 64x281 working journal; archive its exact 214-bit reconciliation key
after all R6/collector completion, then issue a two-sided group reuse permit
only after archive commit and R5-ready ACK. No attention is required before the
next group. Full direct history at 32 B/row is one 288-MiB candidate provision,
not a minimum or measured request use; read_ready adds 18,360 B nominal state.
Descriptor tag activates former reserved-zero bits in an explicit v2 format.
External history traffic/ports/controller/init and current pending-owner reuse
remain open; this is not yet a complete sustained hot/pending/packed backend.

Pure-Python finite checks cover 224 states/499 transitions, six intended
coverage goals and four detected bad-organization counterexamples, including
both close-ACK orders and premature rearm. Archive
format fidelity checks also pass. They prove neither successor RTL nor timing,
full capacity or net benefit. No production RTL/contract change, remote job,
DC or STA. Proposed order is read successor first, then history/second group
only with a physical-service/cost contract, followed by qualified regressions.

## Stage A current-RTL probe result accepted (2026-11-09)

Read [`route_a_stage_a_probe_result_20261109.md`](route_a_stage_a_probe_result_20261109.md)
and JSON. Run `stage_a_continuation_probe_20261109_r1` completed with all four
exits 0, XML 2/2, exact native markers and fresh input/artifact hashes. The
read-only checker reproduces saved results; all 140 source files match the
freeze and checkout, including 24 unchanged main files, and two real native
simulator builds/execution scripts remain. Pane is idle, no live run process.

Each case first completes an actual packed write/read, sidecar, four consumer
commits and one successful terminal. READ_REUSE then accepts the second
attention/plan but holds in binder: no page-ready/member facts, no descriptor
or lease request, no second read. R6 remains Active, the page is readable and
S2 Empty. ADMISSION_REUSE holds legal context/authority/binding at ingress
StateDone with no join; metadata credit occupancy is already zero. These
states are asserted for 128 clocks, not inferred from timeout alone.

Two diagnostic tests PASS; two continuous capabilities remain BLOCKED. The
journal's reset-only namespace is a subsequent static obligation, not a
reached assertion failure. Final retire/reclaim is not reached in these new
probes. Small fixture, gate flag off, external position backing and numeric
correspondence absent remain explicit. No RTL repair, rerun, DC/STA, new
area/timing or net-benefit claim. The next successor must separately address
persistent read activation and cross-group state/journal lifetime; no fix is
implemented by this inspection. Earlier launch/preparation text is historical.

## Stage A current-RTL probes launch snapshot (2026-11-09)

Read [`route_a_stage_a_probe_launch_20261109.md`](route_a_stage_a_probe_launch_20261109.md)
and JSON. Frozen source `0aa5472` was launched in independent
**`kvzap-stage-a-probes-r1:probes`**, run ID
`stage_a_continuation_probe_20261109_r1`, under the existing remote base.
Archive SHA is `e595ed19730dd393693589d7c884ba90eb1cd7febd1c03fd1d6fbb844bad8301`;
all 24 production main files match `097533d`. Actual input gate passes 140
files. Subsequent startup verification has compile exit 0 / COMPILE_PASS
and SIMULATION_BEGIN; test/outer completion and the two bounded blocker
diagnoses are not yet accepted. Elaboration/native simulation results remain
pending, separately from successful Scala compilation.

The user has been notified to wait. Preserve old jobs/inputs, no automatic
retry and no production RTL/DC/STA change. Inspect actual markers, XML,
hashes, first-use data continuity and internal state evidence only after
the user's completion notice; diagnostic PASS is not capability PASS.

## Stage A current-RTL probes prepared (2026-11-09)

Read [`route_a_stage_a_probe_preparation_20261109.md`](route_a_stage_a_probe_preparation_20261109.md).
The user authorizes two independent current-RTL functional probes, with no
production RTL or full DC change. Both first establish a real packed
write/read and successful first terminal, then inspect repeated-read or
second-admission state. Test-only taps observe whole-DUT owners; external
position backing and protocol-only numeric packets remain explicit. The
small test profile uses 16 stream slots to make layer1 legal, gate flag off.
Preparation checks pass; remote compilation and simulation are still pending.
Diagnostic PASS must not be labelled continuous-function PASS. Launch in a
new isolated tmux/workspace with pinned inputs, then notify the user to wait.

## Stage A execution envelope defined (2026-11-09)

Read [`route_a_stage_a_execution_envelope_20261109.md`](route_a_stage_a_execution_envelope_20261109.md)
and its source-pinned JSON. The user authorizes Stage A scope definition.
The event/input/owner/state/observation map separates existing first-use
acceptance from two unexecuted targets: same-page repeated service and
same-session admission of a second group, without reset.

Source tracing confirms an attention terminal leaves R6 Active, and S2
release frees a service slot rather than the persistent packed page. Page
generation stays unchanged between reads; reuse of an S2 slot advances its
source generation. Metadata handoff already returns credit, while ingress
StateDone, reset-only journal ordinals and one-shot activation facts block
the new sustained-use target. The top also lacks an actual Q-vector/data-to-
partial path; initial witnesses must be labelled protocol/control only.

The next bounded batch is to implement/run the two current-RTL probes with
real functional bodies, record exact first blockers, and define any minimum
successor explicitly. No new functional PASS is claimed here. This batch
changes analysis/navigation only; no RTL, simulation, remote job, synthesis
or constraint change occurs. Generic capacity/compatibility, RD1+WCG1 area
reference, PM1 off and RD2 excluded remain preserved.

## Paper execution scope and finite closure target (2026-11-09)

Read [`route_a_paper_execution_scope_and_closure_20261109.md`](route_a_paper_execution_scope_and_closure_20261109.md).
The user directs the next phase toward paper scope, storage contracts,
complete incremental costs and top-level critical timing. The target is a
bounded, repeatable Route-A lifecycle/control prototype for the existing
Qwen3-8B/32K/s1 anchor with a fully stated backend cost/service boundary.
Current first-use/retire acceptance remains valid; reset-free multi-group
admission, repeated page use and a data-linked numeric execution model are
still missing evidence, not silently assumed functionality.

Keep RD1+WCG1 as the measured area candidate, PM1 off/RD2 excluded. Current
primary control delta is 2,967,645.576422 area units; 129.517x is not a full
system ratio. Resolve field lifetime/maximum-live/ports for compact/P3/M2/R5
and diagnose existing-DDC ready/setup chains and common hold-pass behavior
before another RTL candidate/full synthesis. Preserve generic compatibility,
all frozen semantics and 2ns constraints; any lifecycle/interface successor
needs an explicit versioned difference and verification plan. This planning
batch changes documentation only and starts no RTL or remote job. Older
launch-state paragraphs below remain dated historical snapshots.

## RD1+WCG1 full result accepted within scope (2026-11-09)

Read [`dc_rd1_wcg1_full_paired_result_20261109.md`](dc_rd1_wcg1_full_paired_result_20261109.md)
and JSON. Both native sides, all six stage markers, postcheck, full RUN_PASS
and both outer exit-0 records agree. Independent read-only checking reproduces
the saved result and rehashes 136 native artifacts, 4 inputs, 19 bundle files,
189 proxy-tree files and 49 composed SV files. Full-KV primary reproduces the
original/RD1 metrics; its one retained VER-41 diagnostic remains explicit.

Primary Route-A area is 2,990,737.008920, **-11.741151% vs RD1**, ratio
**129.517x**. Wrapper falls 15.492059%; all 366,336 table flops, 4,608 native
gates and 48 driven entry_id bits remain. Gate latches increase sequential
cell count to 581,714; clock root direct loads fall 577,110 -> 215,382 without
removing downstream storage/clock costs. Setup worsens to -0.469940 ns, TNS
-12,698.75 ns / 36,017 paths. Structural cleanliness remains open.

Propagated raw setup is -0.482178 ns. After the identical hold pass, Route-A
setup/hold are -0.575940/-0.034459 ns with 825 hold violations; Full-KV also
has 46 hold violations. The supplemental 119.016x ratio uses its larger
25,372.872553 Full-KV denominator and is not another WCG1 saving. Gate-enable
and gated-table capture hold pass locally, not the whole design. Keep the
measured area candidate and negative timing/hold results separately. No new
RTL, DC/STA job or integration decision is made by this inspection. All
runs are preserved; the current pane is idle bash. PPA, external-service zero
cost, acceleration and hardware net benefit are not established.

## RD1+WCG1 full paired r2 launch snapshot (2026-11-08)

Read [`dc_rd1_wcg1_full_paired_retry_launch_20261108.md`](dc_rd1_wcg1_full_paired_retry_launch_20261108.md)
and JSON. Repair `d680550` passes 48 preparation tests. The successful old
contextual export is reused without RTL regeneration; all real source,
16-port-family/12-owner, R5, 5-proxy and 2-ns static coverage gates pass.
New paired archive SHA is `59306981d8a7fbda704170b48cc69799b6c2424fcb545805032c93d845c4642e`.

Run `dc_feasibility_fair_rd1_wcg1_20261108_r2` is active through the guarded
pipeline in **`kvzap-rd1-wcg1-r2q1:paired-dc`**. After an initial resource-only
admission exit 9 (no native work), the separate q1 dispatcher waits safely at
native admission and then execs the unchanged DC command. Other tasks exited,
and the recorded startup snapshot has active native binding. Formal Full-KV
then Route-A execute automatically only after clean binding. Source freezing
is accepted; native binding/formal completion and area/timing results must
still be verified from markers. Keep primary and both propagated/hold tiers
separate, PM1 off and RD2 excluded. Wait for the user's completion notice;
no automatic retry on failure. The failed r1 and admission-attempt artifacts
are preserved; no other process or input is modified.

## RD1+WCG1 freeze repair (2026-11-08)

The user authorizes the repair and a new full paired run reusing contextual
export r2. Read [`dc_rd1_wcg1_freeze_repair_20261108.md`](dc_rd1_wcg1_freeze_repair_20261108.md)
and JSON: canonical/raw/source hash identities are separated and pinned,
reference equality is byte-exact, and 48 Python preparation regressions pass
including the previously untested freeze-main digest path. No RTL or fair
constraint changed. New immutable run ID is
`dc_feasibility_fair_rd1_wcg1_20261108_r2`; launch and actual execution stage
must be recorded separately. PM1 stays off, RD2 excluded; all three native
policies remain paired. This repair alone is not a new mapped result.

## Latest RD1+WCG1 inspection (2026-11-07)

Read [`dc_rd1_wcg1_full_paired_inspection_20261107.md`](dc_rd1_wcg1_full_paired_inspection_20261107.md)
and its JSON. Contextual export r2 passed with exit 0 (48 reference / 49 gated
SV units), but input freeze failed before native binding and either compile.
The pipeline and full-run outer statuses are both 1; the result root contains
only `exit_status`. No new area, setup/hold, gating or structural result exists.
The tmux panes are idle bash. This inspection runs no DC or simulation and
changes no RTL, frozen script, remote input or process.

The failure is an exact hash-domain mismatch: the freeze script materializes
the 342-byte accepted helper module (`fbc839...`) but compares it with the
381-byte raw emitted-file pin (`aeb38a...`). Current source/raw/prepared
identities and the module body match accepted WCG1 evidence. The reference
wrapper is independently byte-identical to RD1; candidate header, data-field
shape, non-table state and 4,608 source gates pass. These do not replace the
unreached final proxy/profile/native gates. Preserve the failed run and reuse
the completed export only after a separately repaired/tested freeze in a new
bundle/output/run. No automatic retry is started or queued; PM1 remains off,
RD2 excluded, and the original 2-ns numerical constraints unchanged.

## Deep review entry (2026-11-07)

For the research history, evidence chain and current implementation limits,
read [`route_a_deep_review_20261107.md`](route_a_deep_review_20261107.md) and
its [`evidence ledger`](route_a_deep_review_evidence_20261107.json). The
local-only review preserves the original mask/model facts, conditional A4
accounting, bounded first-use/retire PASS, and measured control-area savings.
It does not establish sustained decode, complete incremental affordability,
full-top setup closure, PPA or hardware net benefit. Current RTL has several
Qwen-anchor constants; the generic semantic interface is not evidence of
parameter-only hardware portability.

The paper execution envelope, field lifetime/maximum-live/port contracts,
whole incremental BOM and global combinational timing need explicit closure
before broadening hardware claims or spreading further local optimizations.
A new R2 class-kind compatibility finding is a static candidate requiring
separate directed validation; no failure is reproduced or RTL changed here.
The review includes historical negative results and source-availability limits.

RD1+WCG1 remains the separately authorized pipeline, PM1 off and RD2 excluded.
The last local launch snapshot still has contextual freeze/formal mapping
pending; this review makes no live remote observation. Use
[`dc_rd1_wcg1_full_paired_launch_20261107.md`](dc_rd1_wcg1_full_paired_launch_20261107.md)
and its JSON, and wait for the user's completion notice before inspection.
No new experiment, contract change, input freeze or retry is authorized by
this documentation review.

## Read first

1. [`route_a_document_map.md`](route_a_document_map.md): core versus stage
   evidence classification and retrieval discipline.
2. [`../AGENTS.md`](../AGENTS.md): repository rules and non-negotiable evidence
   boundaries.
3. [`architecture_spec.md`](architecture_spec.md): frozen Route-A semantics,
   owners, atomicity, parameterization, and physical-evidence exclusions.
4. This handoff: current disposition and the next authorized planning target.
5. [`rtl2_phase_contract.md`](rtl2_phase_contract.md): detailed RTL2/RTL3 live
   phase ledger.
6. [`rtl3_9_c4_d_functional_completion_review.md`](rtl3_9_c4_d_functional_completion_review.md):
   current bounded functional-closure decision and its exclusions.
7. [`synthesis_realization_partition.md`](synthesis_realization_partition.md):
   approved SRP scope, classification axes, gates, and stop criteria.
8. [`measurement_boundary_selection.md`](measurement_boundary_selection.md):
   MBR.0 human-approved candidate measurement cut; read
   [`measurement_baseline_fairness_plan.md`](measurement_baseline_fairness_plan.md)
   next for MBR.1's approved paired Full-KV fairness plan, then
   [`full_kv_baseline_path_audit_20261016.md`](full_kv_baseline_path_audit_20261016.md)
   for the completed W0/MR-1A bounded measurement-RTL evidence and the
   separately proposed MR-1B direct-pending contract correction. Read
   [`mr1b_direct_pending_cross_owner_contract_proposal.md`](mr1b_direct_pending_cross_owner_contract_proposal.md)
   only when working on that gap. Neither is a selected
   synthesis top.

Use these only when the question needs the extra detail:

- [`rtl3_8_5_full_path_closure_coverage_contract.md`](rtl3_8_5_full_path_closure_coverage_contract.md)
  for the all-source-subset functional harness and its explicit limits;
- [`rtl_entry_hierarchy_owner_contract.md`](rtl_entry_hierarchy_owner_contract.md)
  and [`rtl_entry_assertion_verification_contract.md`](rtl_entry_assertion_verification_contract.md)
  for sole-owner/interface/assertion rules;
- [`architecture_gate_a_reviewer_02.md`](architecture_gate_a_reviewer_02.md)
  and [`route_a4141_accounted_net_benefit_ledger_contract.md`](route_a4141_accounted_net_benefit_ledger_contract.md)
  for the architecture/DSE evidence boundary.

## What is frozen

- Route-A preserves the original KVzap per-layer/per-KV-head token mask; Route-B
  is frozen backup work.
- A4.11--A4.14.1 research evidence is closed. A4.14.1 remains conditional,
  proxy/accounting evidence rather than measured HBM, speedup, or PPA.
- The ignored A4.14.1 report/input closure is now locally recoverable and
  passing its original read-only preflight; see
  [`a4141_local_provenance_recovery_20261016.md`](a4141_local_provenance_recovery_20261016.md).
  This removes an availability blocker only, not omitted-cost, physical, or
  net-benefit boundaries.
- The architecture contract fixes the common S2 versus Route-A incremental
  split, M2/P3/page/sidecar semantics, legal GQA reuse, R1--R6 owners,
  `metadata_publish_commit` as the single authority linearization point, and
  no Full-KV substitution/fallback.
- Do not reopen pruning, admission, 64-token page size, M2 organization,
  P3 mapping, S2 count, GQA legality, queue/scheduler semantics, or atomic
  commit semantics while planning a separately authorized successor stage.

## Completed implementation phases

| Phase | Current conclusion |
|---|---|
| Gate-A / Gate-RTL0 | Passed at their declared contract/planning scope. Interface manifest, ownership, assertion, environment-assumption, and Python-oracle binding are frozen. |
| RTL1 | Control-plane hierarchy, identity/lifecycle, backpressure, reset, retirement, and verification closure complete. |
| RTL2 | Constrained functional transaction/dataflow closure complete; it is not physical-memory, numeric, or performance evidence. |
| RTL3.0--RTL3.8.5 | Replacement-owner map, functional reference environments, packed/S2 association work, partial/R4 boundaries, and directed all-source-subset coverage complete within their explicit functional/testbench boundaries. Review-03 correctly recorded no RTL3 PASS. |
| RTL3.9-A0/A1/A | R3 is the unique pending-member binding/materialization owner. It drives one exact eight-fragment `pack_read` plus position sidecar through the existing checked R2/R1 path; ingress mismatches fail closed. |
| RTL3.9-B0/B1/B2/B3 | The same immutable member reaches payload durability, R5 descriptor durability, two required M2 member round trips, R5 visibility acknowledgement, exactly one R3 publication acknowledgement, and R6 acceptance of the exact `pending -> packed` authority transition. |
| RTL3.9-C0--C4-D | First owner-correct packed read, S2 READY/source service, terminal/reclaim, accepted-event replay, negative-event coverage, and bounded functional-subsystem review complete. |

### Historical hardware-realization snapshot (2026-10-29)

The project has moved beyond functional RTL closure and measurement-boundary
work into the **first paired DC feasibility execution**.  The stages are
deliberately distinct:

| Layer | Status | What it establishes | What it does not establish |
|---|---|---|---|
| Architecture/A4 ledger | frozen conditional architecture disposition | Route-A semantic and differential-cost accounting scope | physical realization or PPA |
| RTL3.9-C | complete at bounded functional scope | owner-to-owner packed read through terminal/reclaim | physical storage, numeric or controller behavior |
| W0, MR-1A/B and MR-2 | completed within their approved bounded contours | paired DUT owners plus M2/P3/R5/S2 logical array boundaries | macro selection or whole-system inference |
| Projection/wrapper realization | completed for the current successor | parent control retained; functional sidecar/partial/R4 and R5 descriptor backing are typed external boundaries | zero external cost or common-cost cancellation |
| DC input/preflight | passed | exact Full-KV 1-file and Route-A 48-file source lists, typed array proxies and identical fair-v1 constraints | DC result |
| Paired DC feasibility | **completed: tool feasibility pass; timing/cleanliness blocked** | tool/link/netlist/constraint diagnostics for the selected successor | final timing, area, power, PPA or net-benefit conclusion |

The completed run is recorded in
[`dc_feasibility_run_r5_descriptor_externalized_20261029.md`](dc_feasibility_run_r5_descriptor_externalized_20261029.md)
and analyzed in
[`dc_feasibility_result_r5_descriptor_externalized_20261030.md`](dc_feasibility_result_r5_descriptor_externalized_20261030.md).
Both per-top exit markers, source/proxy provenance and mapped netlists pass,
but Route-A misses the frozen 2.0 ns setup target and the hierarchical lint
surface remains open. No raw area or timing number is eligible for a PPA or
net-benefit claim.

The B3 witness is functional control/dataflow evidence only. It does **not**
claim physical M2/SRAM/HBM, controller or CDC behavior, numeric datapath,
frequency, bandwidth, throughput, area, energy, PPA, model/GPU evidence, or a
complete LLM inference engine.

## Current functional closure state

The same production-shaped functional graph has now shown its **first packed
read after publication**, through S2 source service, R6 terminal, and
retirement/reclaim:

```text
R3 publication committed
  + R5 visible descriptor
  + R6 accepted packed authority
    -> packed-read association/demand
    -> existing R2/R1 typed packed read + functional memory environment
    -> exact payload and sidecar deposited into S2 READY
    -> S2 source service / four consumer partial commits
    -> allowed outer functional partial provider and R4 reference boundary
    -> R6 terminal -> retirement -> R5/R6 reclaim
```

The functional memory, attention-partial producer, and R4 merge provider may
remain explicitly replaceable **outer functional environments** during RTL3.
They must not silently become an HBM controller, SRAM macro, attention MAC,
RoPE/exp/FP pipeline, or performance model.

C4-P0 has replayed the frozen event/scoreboard prerequisites from their
immutable source commits. C4-P1 completed the fail-closed C3b event-field
provenance matrix, and C4-P2 is its narrow accepted-carrier precursor. C4-A
binds the eligible R5 old-PageRef/page-free release while keeping
descriptor-invalidate fail-closed because two required fields are not on its
accepted R5 carrier. C4-B success/replay under bounded legal backpressure,
C4-C stale/mismatch, numeric-fault, and reset witnesses, and C4-D's bounded
functional-subsystem completion review are complete. RTL3 functional-subsystem
closure is complete; the next work requires separate authorization and remains
outside physical, numeric, and PPA scope.

## RTL3.9-C0 — association/first-use audit and baseline (complete functional baseline)

C0 keeps R3 as the immutable page/member-ledger owner and treats the existing
`authority_transition_out.fire` as the actual R6 acceptance handshake.  It
does not add an R6 ordinal/page table or a second authority owner.  R3 emits a
read-only page-ready observation only after every ordinal in `[0,
valid_records)` has fired to R6; the activation binder now consumes the real
member-observation stream and requires it to match that summary before it can
query R5 or request an S2 lease.  The exact contract is
[`rtl3_9_c0_post_r6_first_use_association_contract.md`](rtl3_9_c0_post_r6_first_use_association_contract.md).

This is solely a page first-use delay.  It does not change pruning, admission,
page size, M2/P3, GQA, R2 scheduler/FIFO semantics, or R3's single atomic
publication boundary.  C1 remains separately scoped: it must activate only
the post-C0 owner-correct demand/lease path in the composed top.

C0 intentionally permits one completed page association at a time, so a later
member-observation stream is backpressured while the held page awaits/uses its
post-R6 summary.  This is conservative functional flow control because the
member carrier has no `PageRef`; it is not a second authority, admission,
selection, or scheduling mechanism.

## RTL3.9-C1 — post-publication demand activation (complete functional witness)

C1 composes one actual R6-accepted packed-present source-completion plan with
the C0 post-R6 page-ready observation, R5's visible descriptor grant, and
S2's lease through the existing binder and packed-read association owner.  It
observes one exact held registry-allocation request, without modifying the
production top or creating a top/testbench authority, descriptor, plan, or
scheduler producer.  The exact contract is
[`rtl3_9_c1_post_publication_demand_activation_contract.md`](rtl3_9_c1_post_publication_demand_activation_contract.md).

The C1 same-instance Chisel witness passed on 2026-10-14 (one test, zero
failures/errors).  It stops before registry acknowledgement, so it activates
neither C2 typed R2/R1 transport nor functional-memory read data, payload or
sidecar deposit, S2 READY, source service, partial/R4 boundary, terminal,
retirement, or reclaim.

The C0 no-model preflight, binder directed suite, and R3 all-member/ready-low
directed test passed on 2026-10-14.  B3 provenance is replayed from its frozen
commit rather than mutable live source hashes; see
[`rtl3_9_b3_atomic_publication_authority_activation_contract.md`](rtl3_9_b3_atomic_publication_authority_activation_contract.md).

The older C3 prerequisites RTL3.7-B and RTL3.8.3--RTL3.8.5 likewise replay
their hash manifests from their immutable closure commits.  Their historical
validators do not hash mutable descendant source or this living handoff.

## RTL3.9-C2 — functional read-to-S2 closure (complete functional witness)

C2 extends the same B3/C0/C1 instance through the existing allocation bridge,
sole registry, typed R2/R1 path, delivery router, packed payload/sidecar
endpoints, and S2 owner.  One exact payload and sidecar make S2 `READY`; a
stale request identity cannot do so, reset returns the slot to `EMPTY`, and a
matching payload terminal fault makes it `FAULTED` without issuing the sidecar
read.  The test-only composition neither modifies the production top nor
selects a memory/controller/numeric implementation.  The exact boundary is
[`rtl3_9_c2_functional_read_to_s2_contract.md`](rtl3_9_c2_functional_read_to_s2_contract.md).

The endpoint owners retain their established page/generation/slot/ordinal
checks.  C2 does not start source service, partial/R4 work, R6 terminal,
retirement, or reclaim.

## Remaining RTL3.9-C plan

The detailed planned wording is in `rtl2_phase_contract.md`. Work should be
split so that each step has one owner and a reviewable failure boundary:

1. **C3a — packed source service to terminal (complete).** The C2 same-instance
   witness now reaches S2 service, the named partial/R4 environments, four
   packed consumer commits, S2 release, and the sole R6 terminal. See
   [`rtl3_9_c3a_packed_source_service_terminal_contract.md`](rtl3_9_c3a_packed_source_service_terminal_contract.md).
2. **C3b — retirement and reclaim (complete).** The same C3a terminal now
   reaches runtime retirement, the production-shaped drain collector, R6's
   reclaim permit, R5's matching descriptor invalidation/page free, and one
   matching R6 retire acknowledgement. See
   [`rtl3_9_c3b_retirement_reclaim_contract.md`](rtl3_9_c3b_retirement_reclaim_contract.md).
3. **C4-P0 — frozen event/scoreboard provenance (complete; no functional C4
   claim).** The RTL2.4.3, RTL2.5.5, RTL2.6.5c, and RTL3.7-C source-hash
   records replay only at their immutable commits; they are no longer compared
   with mutable descendants. See
   [`rtl3_9_c4_p0_event_scoreboard_historical_provenance_contract.md`](rtl3_9_c4_p0_event_scoreboard_historical_provenance_contract.md).
4. **C4-P1 — C3b event provenance matrix (complete; audit only).** All
   immutable schema records have a fail-closed classification; no event is
   authorized for capture yet. See
   [`rtl3_9_c4_p1_c3b_event_provenance_matrix_contract.md`](rtl3_9_c4_p1_c3b_event_provenance_matrix_contract.md).
5. **C4-P2 — narrow C4-A accepted-event precursor (complete; testbench
   only).** A
   zero-buffer observer binds only authority transition, terminal, and retire
   acknowledgement to their same-fire event records. See
   [`rtl3_9_c4_p2_accepted_event_binding_contract.md`](rtl3_9_c4_p2_accepted_event_binding_contract.md).
6. **C4-A — event-capture precondition audit (complete; no new capture).**
   Terminal, page-free, and retire-ack have complete accepted carriers;
   descriptor-invalidate remains excluded because its required fields are not
   co-carried. See
   [`rtl3_9_c4_a_precondition_audit_contract.md`](rtl3_9_c4_a_precondition_audit_contract.md).
7. **C4-A — eligible event capture (complete; testbench only).** The R5
   page-free release is now a zero-buffer, same-fire observation; terminal and
   retire remain on their P2 bindings. Descriptor-invalidate remains excluded.
   See
   [`rtl3_9_c4_a_eligible_event_capture_contract.md`](rtl3_9_c4_a_eligible_event_capture_contract.md).
8. **C4-B — event replay and bounded legal backpressure (complete;
   testbench only).** The host replay oracle records each selected event after
   its actual handshake and verifies exactly-once order under two-cycle legal
   stalls. See
   [`rtl3_9_c4_b_event_replay_contract.md`](rtl3_9_c4_b_event_replay_contract.md).
9. **C4-C — negative-event precondition audit (complete; no new witness).**
   The existing C3b harness has exact stale/mismatch, R4 numeric-fault, reset,
   and C4-event ingress/observations. Its case matrix records legal prefixes
   and forbidden suffixes. See
   [`rtl3_9_c4_c_precondition_audit_contract.md`](rtl3_9_c4_c_precondition_audit_contract.md).
10. **C4-C — stale/mismatch, numeric-fault, and reset witness (complete).**
    The narrow host-only same-instance witness passed all three directed
    Chisel tests. Its C4 event records are appended only after actual
    handshakes. See
    [`rtl3_9_c4_c_negative_event_witness_contract.md`](rtl3_9_c4_c_negative_event_witness_contract.md).
11. **C4-D — validation and bounded completion review (complete).** Its
    review reconciled C0--C3b and C4-A/B/C without changing an owner or
    datapath; C3b success/replay and all C4-C negative witnesses passed. See
    [`rtl3_9_c4_d_functional_completion_review.md`](rtl3_9_c4_d_functional_completion_review.md).

## RTL3 completion criteria

RTL3 is complete only if a reviewer can verify all of the following for the
declared functional subsystem scope:

- no exercised functional path retains a testbench ingress where a named
  internal owner is required;
- the published packed path above reaches S2, source completion, R4 terminal,
  retirement, and reclaim in one owner-correct functional instance;
- all source subsets have stated ownership and directed success/fault/stall/
  stale/reset coverage, without source-storage owners taking over attention
  computation;
- event capture/scoreboard replay observes owner-produced facts rather than
  inferred testbench defaults;
- publication is still unique, no packed read precedes visibility, each source
  releases only after four GQA consumer updates, and authoritative residency
  remains exactly one;
- any retained outer environments are named and documented as functional-only.

An RTL3 PASS means **functional subsystem closure**, not whole-model inference,
physical implementation, performance, or a Gate-B PASS.

C4-D completed this bounded review on 2026-10-15. The reviewed result is
functional-subsystem closure only.  SRP.0 provenance/source inventory and the
SRP.1-R revised partition proposal passed human review with minor documentary
corrections; SRP.2 source/toolchain eligibility, SRP.3 realization-
requirements decision planning, SRP.4 differential-cost evidence planning,
and SRP.5 completion review are complete at their declared planning scopes.
SRP conditionally passes only to a separately authorized realization-choice
planning review. MBR.0 has begun that bounded `top_future_synthesis_boundary`
planning review, passed its human candidate-cut/BOM review, and authorized
MBR.1.  MBR.1 and MBR.1-A passed external technical review with minor
corrections and received explicit user approval. The targeted Full-KV audit
initially found all three legal baseline path segments absent; W0 has since
completed its bounded dual-DUT functional contour, and MR-1A has completed
its approved Route-A-hot and Full-KV common lifecycle/status integration.
MR-1B direct-pending source-plan association has a contract proposal awaiting
user approval; no MBR review repeats. Independent MR-2 array-only storage
boundary work may proceed without resolving that association. MR-2-P3 has
isolated and directed-tested the P3 functional array interior; see
[`mr2_p3_array_boundary_contract.md`](mr2_p3_array_boundary_contract.md).
MR-2-S2 has isolated and directed-tested the independent S2 payload/sidecar
array-only interior; see
[`mr2_s2_array_boundary_contract.md`](mr2_s2_array_boundary_contract.md).
None of these records selects a
future top or begins physical realization work. See
[`synthesis_realization_partition.md`](synthesis_realization_partition.md)
and its manifest.  No
physical/numeric realization choice, wrapper implementation, synthesis, or
PPA work is authorized by that planning approval.

## Overall path after RTL3

The exact successor gates must be planned and approved after the RTL3 review;
the following is the intended decision sequence, not current authorization:

```text
RTL3 completion review
  -> SRP.0 provenance/source inventory + SRP.1 partition proposal
  -> human review of minimum paper-relevant boundary
  -> SRP.2 source/toolchain eligibility
  -> SRP.3 realization requirements and decision planning
  -> SRP.4 differential-cost evidence plan + SRP.5 completion review
  -> MBR.0 candidate measurement-boundary review + human approval
  -> MBR.1 / MBR.1-A external review + user approval (complete)
  -> Full-KV legal-path source audit (complete)
  -> separately authorized W0 dual-DUT Chisel implementation (complete)
  -> MR-1A Route-A-hot and Full-KV common measurement integration (complete)
  -> MR-1B direct-pending contract approval and scoped implementation
  -> MR-2 independent array-only storage-wrapper realization
  -> synthesizable control/numeric wrapper implementation and verification
  -> targeted synthesis/formal/lint and physical proxy calibration
  -> profiling of the selected realized design
  -> optimization only against measured bottlenecks
  -> timing/area/power evidence and Gate-B review
```

CACTI remains appropriate for explicitly declared SRAM proxy envelopes and
early storage-area/energy sensitivity. It cannot replace a selected macro,
controller, wire/clock, synthesis, timing, or power result. Likewise, DC is
meaningful only after the synthesis-eligible partition, clocks, black-box or
macro assumptions, and numeric/memory wrapper choices have been separately
frozen.

## Measurement RTL live status — 2026-10-21

MR-1A remains complete at its authorized Route-A-hot and Full-KV-common
functional scope. MR-1B B2c has three bounded implementation sub-batches:

1. the reset-only, fixed-64 reconciliation journal/query (`5348de9`);
2. accepted pending-to-packed eligibility withdrawal (`8fe1bba`); and
3. pre-issue R2 candidate cancel/ack, endpoint abort/ack, and the resulting
   R6-owned fault terminal (current directed P2a witness: 4/4 local tests
   passed on 2026-10-21).

The P2a witness was subsequently incorporated into the final bounded MR-1B
acceptance.  The single-record `valid_count = 1` restriction remains in force.

The P2a directed suite has now been reproduced from the clean remote Git
checkout `46ff89a`: `RouteAMeasurementDutR3Spec` passed 4/4 with exit code 0
on 2026-10-21. Its remote log is
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr1b_b2c_remote_p2a_46ff89a.log`.
This confirms the user-local offline Chisel/Verilator platform for this
directed Route-A test; it is not a dual-DUT structural or final B2c closure.

The independent direct-path non-regression has also been reproduced from the
clean remote Git checkout `3d44658`: `RouteADirectPendingReadPathSpec` passed
7/7 with exit code 0 on 2026-10-21. Its log is
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr1b_b2c_remote_direct_nonreg_3d44658.log`.
It confirms the pre-existing direct success/stale/mismatch/withdrawal/fault
contour after P2a; it does not substitute for the remaining latest
reconciliation regression, dual-DUT structural guard, or final B2c coverage
audit.

The earlier Full-KV B2c sideband tie-off issue is resolved by `81b7443` with
an explicit inactive direct-cancel ingress and consumed impossible ack.  The
remote final run passed 14/14 (`EXIT_CODE=0`) across Full-KV baseline,
four-consumer, packed activation, and dual-DUT structural suites; combined
with `c32fffe`'s 22/22 B2c-focused rerun, MR-1B is **PASS at its approved
single-record functional/provenance scope**.  This does not make MR-2, M2
production replacement, synthesis eligibility, DC, or PPA ready.

### MR-2 M2 carrier/provenance closure (2026-10-22)

The minimal M2 production-carrier contract is now implemented and functionally
verified.  The existing pending-payload/location owner supplies immutable,
group-scoped `m2_group_opaque_address_ref` and `m2_group_owner` facts in its
binding.  The admission adapter requires all accepted group members to agree,
relays the facts through the accepted P3 claim, and R3 records them with the
stage.  The two existing M2 group member requests and responses now carry
`kv_head`, opaque reference, and owner; R3 accepts a completion only on an
exact full identity match.  Wrong bank/reference/owner and group disagreement
are fail-closed.

Remote directed evidence is 11/11 passed (`EXIT_CODE=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_carrier_directed.log`;
W0/MR-1A/B2c non-regression and the dual-DUT structural guard are 27/27
passed (`EXIT_CODE=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_carrier_nonreg.log`.
The carrier's adapter/stage/outstanding-register control is recorded as
Route-A incremental, unestimated-not-zero BOM cost.

M2 carrier provenance and the bounded measurement-DUT production-control
replacement were closed before entry-data lowering. `RouteAMeasurementDut`
instantiated `RouteAM2ProductionControlOwner` with eight-bank mirrored
head/span control provenance plus a 36-stage exact two-member gate. Its
then-final directed remote regression was
4 suites/14 tests passed, `EXIT_CODE=0`, at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_owner_final_directed.log`.
The required W0/MR-1A/B2c non-regression is also 6 suites/27 tests passed,
`EXIT_CODE=0`, at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_owner_nonreg.log`.
The earlier precheck is retained only as a precheck because its intended
measurement-DUT selector used the wrong package.  The required M2
storage-array provenance audit is recorded in
`analysis/mr2_m2_entry_update_provenance_gap.md`: current carriers have no
legal entry/update-data producer, entry layout, RMW operand, write-enable, or
storage-fault source. That historical block was resolved only by the later
approved minimal-runtime implementation below; it was not resolved by
repurposing an address, owner, or fixture as entry data. No macro, physical
address, timing, energy, area, synthesis, DC, or PPA conclusion follows.

The implementation-level declaration review is now recorded in
`analysis/mr2_m2_entry_update_declaration_contract_proposal.md`. It separates
the frozen 59/50-bit (64/64 padded) semantic-accounting envelopes from real
entry words and finds no current production data-decision owner. Before M2
storage RTL, four explicit choices remain: entry encoding/validity, head/span
key and reuse rule, lifecycle-to-RMW lowering with one declaration producer,
and typed storage-fault encoding. The proposed declaration is a single data
carrier only; it cannot change R3 atomic publication, admission, R6 authority,
or R2 arbitration. Its future producer/peripheral/array costs are Route-A
incremental and `unestimated_not_zero`.

The final MR-2 four-decision approval proposal is
`analysis/mr2_m2_four_design_decision_proposal.md`. Its preferred package uses
128-bit real head/span entries, a 614-slot generation-tagged span pool, and
generic fail-closed storage faults; the entry arrays alone are 152,320 bits
(2.84× the frozen 64-bit accounting proxy) before tags, queues, or peripheral
logic. Crucially, frozen A4 M2 records require explicit private/shared
source-FIFO and create/dequeue/release facts that are absent from the current
non-contiguous R3 packed group. Approval must therefore include one explicit
upstream metadata-lifecycle declaration producer. Without that producer, only
the current provenance journal is implementable and it must not be labelled M2
storage realization.

### MR-2 minimal admission-to-metadata bridge (2026-10-22)

The first approved minimal-runtime implementation sub-batch is now live in
`RouteAMeasurementDut`. `RouteAAdmissionPublicationIngressAdapter` emits a
`MetadataAppendMemberDeclaration` only on the same accepted fire as the
existing retained admission context, R6 authority, and exact pending-payload
binding. `RouteAMetadataAdmissionBridge` therefore records an actual immutable
binding rather than reconstructing membership from group tag, ordinal, mapping
reference, or a fixture. It holds one bounded group entry per P3 layer,
up-to-64 exact member bindings, a local/shared/staging logical-credit
classification, and a 16-bit per-stream append sequence. It gates pre-accept
admission with ready-low before the triple fires; it neither revises the
admission disposition nor creates R3 publication, R6 authority, source
selection, or R2 arbitration.

The bridge forwards the pre-existing M2 group prepare only after the exact
member mask is complete. Publication faults keep pending membership and credit
while discarding only private preparation. Credit is released only from the
non-backpressuring R3 observation that the corresponding all-member post-R6
handoff has fired. At this bridge-only checkpoint, it was not yet the grouped
entry-data prepare/commit/abort or actual M2 entry storage. Those bounded
production pieces are implemented in the following record; the M2 array-only
boundary remains separately open. Its state is Route-A incremental and
`unestimated_not_zero` in `analysis/measurement_boundary_bom.json`.

Remote directed evidence is 4/4 passed (`EXIT=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_admission_p1_indexfix_20261022.log`:
non-contiguous real members, duplicate rejection, private prepare, publication
then all-member handoff release, and local-to-shared bounded credit fallback.
The previous dynamic stream-index width warnings were removed before this run.
The current-source dual-DUT elaboration/structural guard is 3/3 passed
(`EXIT=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_admission_p1_structural_20261022.log`.
Neither bridge-only result alone was an M2 entry-data/storage realization,
synthesis eligibility, or physical-cost conclusion.

### MR-2 M2 grouped entry-data production integration (2026-10-23)

The approved bounded-runtime lowering is now integrated in
`RouteAMeasurementDut`. The existing accepted retained-member declaration
enters `RouteAMetadataAdmissionBridge`; the bridge preserves immutable full
member bindings, credit class, and append sequence, and fires
`MetadataAppendOperand` only jointly with the pre-existing R3 M2 group
prepare. `RouteAM2ProductionControlOwner` validates the exact member mask and
binding provenance, reserves private head/span state, and returns the two
existing typed M2 member responses. It returns OK only after joint validation
of both objects; a failed validation produces the existing typed fault and
private abort rather than a partial update.

The real bounded entry state is two mirrored 128-bit head entries for each of
288 head keys and one 128-bit span entry for each of 614 slots (152,320 entry
bits before occupancy/generation and peripheral state). Both head replicas and
the matching span become visible together only on the existing accepted
`metadata_publish_commit`/Published resolution. A publication fault or reset
clears only private state and retains legal pending membership and credit.
Only the exact non-backpressuring post-R6 all-member handoff clears a visible
entry, advances its generation for stale-safe reuse, and releases bridge
credit. Generation wrap remains fail-closed.

Evidence is remote 11/11 directed (`EXIT=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_grouped_p1_entryverify_20261022.log`,
followed by remote 40/40 selected W0/MR-1A/MR-1B/M2/dual-DUT non-regression
(`EXIT=0`) at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_grouped_p1_full_nonreg_20261022.log`.
The evidence includes pre-publication invisibility, joint member completion,
typed semantic fault/abort, publication fault, reset, exact post-R6 handoff
release, credit fallback/release, stale/duplicate rejection, Full-KV
lifecycle/fault/reset, packed/hot/direct-pending paths, and the dual-DUT
structural guard.

This closes **bounded functional M2 production entry-data integration** only.
It did not at that point close the M2 array-only boundary, select an
SRAM/macro or ports, or turn functional storage into physical/PPA evidence.
The boundary result is recorded next; M2 queue/staging activity and wrapper
cost remain `unestimated_not_zero`, and the old fixture-only
`RouteAM2EntryStorage` remains separate from the production result.

### MR-2 M2 logical entry-array boundary (2026-10-24)

`RouteAM2EntryArrayBoundary` now owns only the bounded functional entry-word
interior: 288 logical head keys with two mirrored 128-bit head-control entries
each, plus 614 logical 128-bit span-owner entries. It accepts only parent-owned
already-decided publication-commit and all-member-handoff-release updates. The
production owner still exclusively owns accepted operand association, immutable
validation, RMW decision, private prepare/abort, slot and generation control,
credit, typed faults, `metadata_publish_commit`, and post-R6 handoff
qualification. Both updates may occur in one cycle only for distinct logical
locations; the boundary asserts that condition and mirrored-head equality.

The boundary structural/preflight suite passed locally (8 tests, including all
four M2/P3/S2/R5 boundary guards and MBR/SRP validators). Remote targeted
evidence passed 3 suites / 11 tests, `EXIT=0`, at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_array_boundary_p0_20261023.log`.
Remote selected W0/MR-1A/MR-1B/M2/dual-DUT non-regression then passed 10
suites / 40 tests, `EXIT=0`, at
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/mr2_m2_array_boundary_p1_full_nonreg_20261023.log`.

This closes **only the logical functional M2 entry-array boundary**. It does
not select a memory macro, physical banking/ports/latency, controller,
queue/staging activity model, DC, CACTI, timing, area, power, throughput, or
PPA conclusion. Those retained and unestimated items must be addressed by the
separate realization-preparation stage.

### MR-2 R5 logical availability/generation boundary (2026-10-25)

`RouteAR5AvailabilityArrayBoundary` is now the sole logical owner of the R5
availability/generation vectors. `RouteAPageManager` retains allocation choice,
PageRef/generation validation, descriptor visibility, durable
invalidate-before-free, reclaim, drain/reset/init, and all descriptor-service
and wrapper-peripheral behavior. Remote directed R5 evidence passed `21/21`;
the latest-source selected cross-stage evidence passed in two non-overlapping
invocations totalling `40/40`. The record is
[`mr2_r5_availability_array_boundary_contract.md`](mr2_r5_availability_array_boundary_contract.md).

This closes only the logical functional R5 array boundary. It does not select
an R5 macro, ports, latency, descriptor service, controller, DC, CACTI, or
PPA, and all remaining storage/access costs remain `unestimated_not_zero`.

### MR-2 completion review (2026-10-25)

MR-2 now passes at its approved **functional measurement-boundary** scope:
P3 stage, S2 payload/sidecar, M2 entry, and R5 availability/generation
interiors are separated while every parent-owned protocol, atomicity,
identity/generation, lifecycle, reset, and external-service control remains
in the candidate DUT. The review is
[`mr2_completion_review.md`](mr2_completion_review.md). It neither selects
physical storage nor authorizes synthesis/PPA. The next bounded task is the
dual-DUT measurement-cut freeze, before any realization-choice work.

### Dual-DUT measurement-cut freeze (2026-10-25)

The actual `FullKVMeasurementDut` and `RouteAMeasurementDut` instance/source
lists, outer interfaces, cost classifications and single-record direct-pending
limit are frozen at `fc06fdbc`. The record is
[`measurement_dut_cut_freeze_20261025.md`](measurement_dut_cut_freeze_20261025.md)
with its machine-checked JSON inventory. It confirms actual shared R2/R1/
delivery classes, but deliberately records non-identical Full-KV S2/lifecycle
classes and the absent same-class Full-KV hot owner as **not automatically
cancellable**. The next gate is a separately approved realization-preparation
review; this freeze does not select a synthesis top or physical wrapper.

### Synthesis-top candidate selection (2026-10-25)

The two future control-top candidates are selected conditionally from the
frozen measurement DUT projections, while `RouteAKVSubsystemTop` remains
rejected as a composition skeleton. The review
[`synthesis_top_candidate_selection_review.md`](synthesis_top_candidate_selection_review.md)
records retained/excluded controls, outer boundaries, no-wholesale-black-box
rules and the pre-DC stop conditions. In particular, actual shared R2/R1/
registry/router classes do not resolve the Full-KV hot and S2/lifecycle
equivalence differences. The next permitted work is wrapper-interface planning
and common-equivalence disposition, not RTL, macro selection, DC or PPA.

The EDA-server Chisel platform is user-local and offline. See
[`chisel_platform_handoff_20261021.md`](chisel_platform_handoff_20261021.md).
Future remote implementation work must use a provenance-preserving Git checkout
rather than the earlier rsync-only platform smoke snapshot.

### Realization-preparation wrapper/common disposition (2026-10-25)

The first post-selection decision package is now review-ready in
[`realization_preparation_wrapper_common_disposition.md`](realization_preparation_wrapper_common_disposition.md)
with a machine-checked manifest.  It proposes typed future access contracts
for M2, P3, S2 and R5 array interiors, retains their named parent control and
adapter/peripheral cost, and keeps R5 descriptors external.  It also resolves
the current fairness stance conservatively: only identical R2/R1/registry/router
shells can become common later; Full-KV S2 and lifecycle/status are not yet
cancellable, and the actual Route-A-only hot source is Route-A differential
until a successor freeze proves a legal baseline counterpart.  R4 numeric,
partial-provider, external memory, P3 pending backing and R5 descriptor service
remain named nonzero external/unestimated responsibilities.

Human approval has authorized the bounded wrapper-RTL work package.  The first
M2 parent-side keyed lookup plus publication/handoff commit-ack adapter is
functionally verified on remote successor `3f3a489`: the owner suite is 5/5,
the direct array-boundary suite is 1/1, and the current-source W0/MR-1A/MR-1B/
M2/dual-DUT cross-stage suite is 10 suites / 40 tests, all with exit 0. It
replaces the whole-array parent views without moving M2 membership, credit,
RMW, private prepare/abort, publication, stale, reclaim, or authority control
into the array child. Its adapter/provenance-index cost remains Route-A
incremental `unestimated_not_zero`. This selects no macro, physical port count,
latency, clock, controller, numeric unit, DC/CACTI or PPA. The next wrapper
implementation sub-batch is R5 parent-side availability/generation access;
each later wrapper batch still requires a successor source/port freeze, not
synthesis itself.

### R5 parent-side availability/generation adapter (2026-10-26)

Successor `3aab1ce` replaces PageManager's direct whole-array availability and
generation views with `r5_availability_access_v1`: a registered keyed lookup,
an allocation-update ack, and a typed four-lane reclaim-generation-update ack.
PageManager still selects the free key with a bounded scan, forms/validates
PageRefs, owns descriptor visibility and reclaim sequencing, and releases an
old PageRef only after the matching child reclaim ack. The child remains unable
to create allocation, reclaim, release, publication, authority, or terminal
facts.

Remote directed evidence is `15/15`: boundary/reclaim `6/6` at
`r5_parent_adapter_directed_f4b35ca_rerun.log`, then R3/R5 publication/reset
`9/9` at `r5_parent_adapter_pubfix_3aab1ce.log`. The current-source selected
cross-stage evidence is additionally complete: `10` real suites / `40` tests
on the unchanged R5 production RTL, using the six real suites from
`r5_parent_adapter_p1_full_nonreg_a60e525.log` plus correct-package reruns at
`r5_parent_adapter_p1_missed_suites_a60e525.log` and
`r5_parent_adapter_p1_owner_direct_bfa441c.log`. Four initial `0/0` selector
outputs are explicitly excluded; `bfa441c` only makes owner-fact test timing
wait for the required allocation ack.

This is a functional wrapper adapter result only. The availability interior
plus parent scan/ack peripheral remain Route-A incremental
`unestimated_not_zero`; no macro, port count, latency, descriptor controller,
DC, CACTI, or PPA result follows. A successor source/port freeze is still a
separate gate; P3/S2 wrapper RTL was the remaining approved sequence.

### P3 parent-side stage/sidecar access adapter (2026-10-27)

Successors `c3ec15d` through `0023e76` complete the next approved P3 wrapper
sub-batch. `RouteAP3StageArrayBoundary` now provides typed payload-write and
sidecar-write request/ack paths plus a held, tagged payload-read response.
`RouteAM2P3Wrapper` still owns all P3 control: claim/generation, accepted
member/binding ledger, order checks, materialization, packed-write sequence,
durability, M2 publication, R6 observation and release. A payload or sidecar
ingress fire cannot advance its parent order/state until the exact child ack;
a packed-write data beat cannot issue before the exact tagged payload-read
response.

Remote evidence at current successor `0023e76` is `EXIT_CODE=0`, with
`RouteAP3StageArrayBoundarySpec` 1/1 and the narrow parent/publication probe
`RouteAR3R5PublicationSpec` 6/6, recorded in
`p3_parent_adapter_isolated_rerun_0023e76.log`. The parent probe is deliberately
flat because the remote ChiselSim DPI generator cannot expose a pre-existing,
unrelated B2c nested direct-pending association as a root port; no production
carrier is tied off or changed. The root-level materialization test is not
current remote evidence for this reason.

This verifies only the functional logical P3 array/access boundary. P3
payload/sidecar interiors and parent request/ack/read-response peripheral are
Route-A incremental `unestimated_not_zero`; the pending-HBM backing remains a
separate external service. No macro, physical port count, timing, controller,
DC, CACTI or PPA result follows. The remaining approved Route-A wrapper
sub-batch was S2.

### Route-A S2 payload/sidecar parent-access adapter (2026-10-27)

The S2 sub-batch is now complete for the Route-A contour.  The parent
`RouteAS2GqaSourceWrapper` keeps all source/lifecycle control and accesses
`RouteAS2PayloadSidecarArrayBoundary` through typed payload and sidecar write
request/acknowledgement plus read request/response paths.  Parent order moves
only after the exact child write acknowledgement; reads are authorized by the
parent while READY and their external response is held by the parent.  Thus
the child has no identity/generation, READY, four-consumer, release, fault, or
authority ownership.

Remote directed evidence is `9/9` (`RouteAS2DirectPendingSpec` 3/3 and
`RouteAPackedS2ReadPathSpec` 6/6) in
`s2_adapter_directed_rerun.log`, `S2_ADAPTER_RERUN_EXIT=0`.  The selected
cross-stage result is Route-A measurement 4/4, Full-KV measurement 5/5
non-regression only, dual-DUT structural 3/3, and four-consumer 3/3.  The
initial combined run had a fixed-cycle terminal-ready test assumption after a
child write; the explicit ack-aware rerun is
`s2_fourconsumer_rerun.log`, `S2_FOURCONSUMER_RERUN_EXIT=0`.

This Route-A logical functional-wrapper result is now followed by a bounded
Full-KV payload-only successor.  `FullKVS2GqaSourceWrapper` retains all
baseline-local lifecycle ownership and accesses a typed
`full_kv_s2_payload_array_boundary` through parent-owned write-ack and
read-response paths.  The remote rerun passed `FullKVMeasurementDutSpec` 5/5
and `DualMeasurementDutStructuralSpec` 3/3 (`fullkv_s2_directed_rerun.log`,
`FULLKV_S2_RERUN_EXIT=0`).  It covers READY after the matching child ack,
exact read identity/generation, held read response, stale, fault, reset,
four-consumer completion, release, and retire/drain.

This remains a pair of functional payload adapters, **not** a paired S2 common
implementation.  Full-KV has no Route-A sidecar/packed logic, and payload or
adapter cost cannot cancel until the ordered paired access-map and
shell-equivalence disposition is complete.  Neither this record nor the
preceding P3/M2/R5 results choose a macro, physical port count, latency, clock,
controller, DC, CACTI or PPA.

The immutable cut-freeze at `fc06fdbc` is not rewritten by wrapper successors.
Its current source-SHA guard reports the already recorded P3 incremental-source
drift and the new S2 common-source drift.  This is a provenance status, not a
functional failure.

### Paired S2 payload access-map disposition (2026-10-28)

The Full-KV S2 successor now makes the two payload parent-to-child routes
comparable.  The map in
[`s2_paired_access_map_common_equivalence_disposition.md`](s2_paired_access_map_common_equivalence_disposition.md)
confirms the same logical roles for validated payload write/ack, READY-gated
read/response, parent-held response under backpressure, and exclusion of
identity/generation/lifecycle/authority from either child array.

The conclusion is deliberately **not** that the S2 cost is now common.  Route-A
retains sidecar plus packed lease/page and R6-path control; Full-KV retains a
parameterized payload geometry and baseline-local lifecycle/fault shell.  Both
payload interiors/adapters remain named nonzero costs.  A common payload result
requires a same-parameter future shell, explicit wrapper equivalence, paired
reset/init/stale/fault/release conformance, and the successor source/port/filelist
freeze.  The P3 full-root ChiselSim DPI harness recovery is now complete. The
test root is `RouteARTL39AMaterializationHarness`, which contains the unchanged
production `RouteAM2P3Wrapper` and flattens only the fields asserted by
`RouteARTL39AMaterializationSpec`; it is not a production wrapper or a
substitute for the candidate/delivery paths. Remote evidence is
`p3_fullroot_dpi_harness_20261028.log` (3/3, exit 0) and
`p3_fullroot_dpi_nonreg_20261028.log` (P3 boundary 1/1 plus R3/R5 publication
6/6, exit 0).

The ordered next work is the successor source/port/filelist freeze and paired
shell conformance. Before any common-cost cancellation, it must resolve the
Full-KV focused 3-bit geometry versus Route-A anchor 9-bit/512-fragment
geometry: prove a legal same-configuration implementation or retain the
realized difference as separately nonzero cost. This recovery neither chooses
physical storage nor starts DC/CACTI/PPA.

### Successor source/port/filelist freeze (2026-10-28)

The successor record
[`successor_synthesis_source_port_filelist_freeze_20261028.md`](successor_synthesis_source_port_filelist_freeze_20261028.md)
now pins the current two candidate tops, their live outer ports, the twelve
main Scala dependency sources, build inputs, SHA-256 values and intentional
exclusions. It adds Full-KV's real payload read request/response outer boundary
to the earlier `fc06fdbc` cut, excludes the rejected composition-only top and
uninstantiated Package-A storage candidate, and keeps all test harnesses out
of the synthesis input set.

The successor paired 9-bit regression is complete: `FullKVMeasurementDutSpec`
5/5 and `RouteAPackedS2ReadPathSpec` 6/6 passed together in
`s2_paired_9bit_conformance_20261028.log` with exit 0. This resolves the
focused Full-KV 3-bit geometry as a functional-conformance gap, but not as a
common-cost decision: the two shells remain non-identical, and Route-A sidecar,
packed lease/page and R6 controls remain incremental.

### Dual synthesis-top input package (2026-10-28)

[`dual_synthesis_top_input_package_20261028.md`](dual_synthesis_top_input_package_20261028.md)
converts the successor freeze into a pre-DC inventory for the two selected
control-top projections. It fixes their admissible Scala closure, exact
outer-port lists, retained parent controls, array-only boundaries, external
and functional-reference contracts, paired 9-bit conformance restriction, and
nonzero integration-shell responsibility. It expressly records that neither a
projection generator nor generated HDL/DC filelist exists yet: the current
parameterized measurement DUTs cannot be sent directly to DC because the
Route-A functional reference classes must first be externalized rather than
synthesized or tied off. That package is a pre-implementation inventory. Its
later P1 successor below does not retroactively alter this frozen record. No
DC/CACTI/PPA is authorized.

### Control-projection P1 externalization (2026-10-28)

The bounded implementation record is
[`control_projection_p1_externalization.md`](control_projection_p1_externalization.md).
`FullKVControlProjection` and `RouteAControlProjection` now construct the
selected measurement-DUT controls directly; `RouteAKVSubsystemTop` remains
excluded. Route-A externalizes the former functional sidecar-delivery child by
typed work/release/allocation/issue ports, removes the stateless functional
partial-provider pass-through in favor of the original typed outer ports, and
retains only an internal R4 packet/result/fault protocol adapter while numeric
work remains external.

Remote `ControlProjectionElaborationSpec` passed 1/1 with
`PROJECTION_P1_ELAB_EXIT=0` in
`projection_p1_elaboration_rerun_20261028.log`. This is an elaboration guard
using the pre-existing paired functional profile, not final HDL or a physical
profile. The explicit externalization BOM delta is
[`control_projection_p1_bom_delta_20261028.json`](control_projection_p1_bom_delta_20261028.json):
all new boundary/adapter and external-service rows remain nonzero and
unestimated. The next bounded activity is to choose one explicit, bounded
control-projection parameter profile; it must not consume
`RouteAR6Encoding.testOnlyAnchor`.

### Paired bounded control-projection profile (2026-10-28)

[`paired_control_projection_profile_20261028.md`](paired_control_projection_profile_20261028.md)
records `qwen3_8b_32k_s1_control_projection_v1`, the common explicit parameter
object for `FullKVControlProjection` and `RouteAControlProjection`. It is not a
third top: the two emitted module names remain `full_kv_control_projection` and
`route_a_control_projection`. The profile binds the A3 36-layer/8-head/32K/s1
control anchor to 146,880 logical R5 pages, 288 streams, 9-bit/512-fragment
geometry, bounded R2/context capacity, and explicit non-test-only association
encodings.

Remote `RouteASynthesisControlProjectionProfileSpec` passed 1/1 with
`PAIRED_CONTROL_PROFILE_EXIT=0` in
`paired_control_projection_profile_20261028.log`. The profile check validates
the Scala object only; it intentionally does not elaborate the large full
profile or generate HDL. The bounded control-state BOM delta is
[`paired_control_projection_profile_bom_delta_20261028.json`](paired_control_projection_profile_bom_delta_20261028.json).
It retains all newly sized control, wrapper, external-memory and numeric rows
as nonzero/unestimated, and does not authorize DC/CACTI/PPA.

### Paired generated control-projection HDL freeze (2026-10-28)

[`paired_control_projection_hdl_freeze_20261028.md`](paired_control_projection_hdl_freeze_20261028.md)
and its JSON companion now freeze actual generated SystemVerilog for the
approved `qwen3_8b_32k_s1_control_projection_v1` profile:
`full_kv_control_projection` is one SV compilation unit and
`route_a_control_projection` is a recursive 182-SV split compilation unit,
each with an independent exact `.f` file.  The archived artifact has SHA-256
`335942f0f01c24124b1fda56c6ebbd8b3425afdb2c31220cac04ff871aa94310`.

The generated-HDL structural verifier passed both top/module/filelist checks
and confirmed typed external boundaries plus exclusion of the composition
skeleton and retired functional-reference modules.  Nine post-emission semantic
suites passed 34/34 actual tests; the complete dual-DUT structural guard passed
3/3 by CHIRRTL elaboration.  The guard changed only from a failing ChiselSim
DPI wrapper to same-root CHIRRTL elaboration; it neither narrows DUT IO nor
changes production control.

This is a pre-DC input freeze only.  The companion
[`paired_control_projection_hdl_bom_delta_20261028.json`](paired_control_projection_hdl_bom_delta_20261028.json)
retains all parent controls/adapters and external sidecar/partial/R4/memory
services as nonzero or unestimated.  Direct-pending remains single-record;
S2 remains non-cancellable.  A later, separately authorized DC-feasibility
batch must first supply library/link, clock/reset, black-box/array and
external-service declarations, then inspect actual synthesis connectivity and
optimization.  No DC, macro, area, timing, power, PPA or net-benefit claim is
authorized by this freeze.

### DC environment preflight (2026-10-29)

[`dc_environment_preflight_20261029.md`](dc_environment_preflight_20261029.md)
records that `dc-server` has an executable Synopsys `dc_shell O-2018.06-SP1`
and the inherited TSMC28 standard-cell `.db` candidates under the existing
`dc_project/pdk` root.  The explicit sourceable environment and read-only
preflight live in `hardware/route_a/dc/`; they verify the selected feasibility
library path, frozen HDL archive hash, and the independent 1-SV Full-KV and
182-SV Route-A filelists without invoking DC.  The 2026-10-29 remote preflight
passed with candidate-library SHA-256
`5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.
Clock/reset constraints,
array/black-box treatment and external-service stubs remain intentionally
unselected and are the next separately authorized DC-feasibility inputs.

### DC constraint contract (2026-10-29)

[`dc_constraint_contract_20261029.md`](dc_constraint_contract_20261029.md)
adds a static-checked `hardware/route_a/dc/constraints_control_projection.tcl`
for either frozen top.  It fixes the single `clock`/synchronous `reset`
interface rule and constrains reset rather than hiding it with a false path.
It deliberately requires an approved run manifest to specify all period,
uncertainty, I/O delay/transition and output-load numbers; none is inherited
from H3.  The resulting contract is ready, but numerical constraints,
array/black-box treatment and external-service stubs remain required before a
separately authorized DC-feasibility invocation.  The remote static contract
check passed for both actual generated roots; the server has no standalone
`tclsh`, so only the future authorized DC Tcl source will perform the final DC
parser check.

### `dc_feasibility_fair_v1` numerical constraint freeze (2026-10-29)

[`dc_feasibility_fair_v1_constraint_freeze_20261029.md`](dc_feasibility_fair_v1_constraint_freeze_20261029.md)
freezes the first paired DC feasibility profile: 2.0 ns period, 0.10/0.02 ns
setup/hold uncertainty, 0.20 ns I/O delays, 0.05 ns input transition and
0.005 pF lightweight top-level output load under the inherited TSMC28 LVT SSG
library.  It applies identically to both generated top roots; reset is timed
as a synchronous input, with no false-path or multicycle exception.  A static
coverage report will enumerate every actual top port, but DC's ignored-
constraint and unconstrained-path reports remain required during the later
authorized run.

The freeze also makes the remaining readiness block explicit: M2/P3/R5/S2
array interiors need a typed generic black-box/stub materialization before DC;
their parent control/peripherals stay in RTL.  Current external services are
typed top-level ports but still require an interface-conformant harness/stub
and nonzero/unestimated cost treatment.  No behavioral array may be treated
as free synthesized logic, and no DC launch is authorized by this record.

### DC feasibility fair-v1 input readiness (2026-10-29)

[`dc_feasibility_input_readiness_review_20261029.md`](dc_feasibility_input_readiness_review_20261029.md)
accepts the approved fair-v1 manifest and static coverage: the actual frozen
Full-KV root has 41 ordinary inputs/36 outputs, Route-A has 244/115, and both
have zero static unconstrained ports under the collection-based single-clock
contract. DC-native ignored-constraint and unconstrained-path evidence is
still deferred until an authorized run.

The typed M2/P3/R5/S2 array-interior successor is now materialized and checked
on the EDA server; see
[`dc_array_proxy_materialization_20261029.md`](dc_array_proxy_materialization_20261029.md).
It replaces only five same-header array bodies, retaining all parent controls.

The later R5 descriptor externalization produces a distinct, immutable
successor package: its Route-A HDL is the valid 48-file split lowering rather
than the earlier 182-filelist source.  The static proxy and constraint checks
for that package pass; the authoritative record is
[`dc_successor_input_preflight_r5_descriptor_externalized_20261029.md`](dc_successor_input_preflight_r5_descriptor_externalized_20261029.md).
The selection removes functional descriptor backing from the projected control
closure through a typed external service port, while retaining page-manager
control and treating every array/external service as nonzero/unestimated.
This is only a pre-DC input result: behavioral arrays must not be treated as
free logic and no DC/PPA claim follows.  The remote selected parent-control
suite passes 33/33 actual tests. `RouteAMeasurementDutR3Spec` is explicitly
still blocked before assertion execution by the known full-root ChiselSim
C-DPI bridge defect for its deep B2c association port; this is a test-harness
repair item, not a passing full-root result or a proxy semantic failure.

### DC control-realization diagnosis and refinement P1 (2026-11-01)

[`dc_control_realization_diagnosis_20261101.md`](dc_control_realization_diagnosis_20261101.md)
localizes the first fair-v1 Route-A size diagnostic using the saved DDC and
native reports, without rerunning DC.  The two dominant owners are
`route_a_m2_p3_wrapper` and `route_a_metadata_admission_bridge`; the latter's
662,404 mapped sequential cells are accounted exactly by a duplicated
`36 x 64 x 281-bit` pending-binding ledger plus 14,980 other bits.  A DDC
probe also proves that the reported 1,298,154-load
`directPendingIssue/net188753` is the top clock's transient compiler alias,
not a direct-pending data broadcast; reset reaches only 67,632 endpoints.

The first bounded refinement removes only the duplicate full binding ledger
from the metadata-admission bridge.  R3/P3 retains the full membership facts;
the bridge retains the exact 64-bit member mask plus immutable mapping
reference/owner and fails closed on later-member or preparation mismatch.  M2
continues to validate every group-summary field it consumes.  The pre-DC state
calculation predicts a 645,012-bit reduction, but this is not yet an observed
mapped-area result.  The remote directed production suites pass 8/8 in
`control_refine_p1_20261101.log`; successor HDL checks and an
unchanged-fair-v1 DC comparison remain required before accepting an area,
timing, fanout or lint improvement.

The initial cross-stage P2 run passed 37/41 tests and localized all four
failures to the `RouteAMeasurementDutR3Spec` simulator root before behavioral
execution.  The functional DUT now drives its projection-only R5 descriptor
service dormant in non-projection mode.  A test-only
`RouteAMeasurementDutR3Harness` also keeps the complete production DUT as its
sole child while excluding unused deep sidecar ports from ChiselSim's broken
long-name DPI ABI; it changes no production connection.  Remote P4 passes the
four actual same-instance behavioral cases 4/4, including packed reclaim, hot
terminal, stale response and direct-transition cancellation/fault.  The
preserved log is `control_refine_p4_r3_harness_20261102.log`.

The clean P5 cross-stage rerun passes 10 suites / 41 actual tests with no
failures, cancellations or ignored cases and
`KVZAP_CONTROL_REFINE_P5_FULL_P2_EXIT=0`.  The authoritative log is
`control_refine_p5_full_p2_20261102.log`.  This closes the functional
non-regression gate for refinement P1.

The 48-file refined Route-A successor and paired typed-array proxy then pass
the generated-source gate recorded in
[`dc_control_refinement_successor_20261102.md`](dc_control_refinement_successor_20261102.md).
All 16 required typed port families, 12 production control owners, four raw
Route-A array interiors and five paired proxy boundaries pass.  The generated
metadata bridge has 17,492 logical state bits versus 662,504 in the old raw
successor, a source-level reduction of 645,012 bits.  The paired archive SHA is
`1b5ac01cd35c77c37c6d7a08843c8554ec2458eb25cc9d7d6cafbefc873ec33d`.
This closes the refinement's pre-DC source/proxy gate; same-fair-v1 DC remains
pending, so no mapped cost, fanout, lint or timing improvement follows yet.

### Paired successor DC result (2026-11-03)

The bounded same-constraint comparison is complete; the authoritative result
is
[`dc_control_refinement_result_20261103.md`](dc_control_refinement_result_20261103.md).
Both per-top exits, paired `RUN_PASS`, outer exit, hashes, typed proxies, DDCs,
mapped HDL and native reports close.  Full-KV exactly reproduces the baseline.

Route-A mapped cell area falls from 6,716,537.642416 to 3,952,935.893452
(-41.146%).  Sequential cells and the transient clock-alias load both fall by
exactly 645,012, while the metadata-admission bridge hierarchy falls 96.973%.
This accepts the intended mapped-area and clock-load improvement at the fixed
logic-only DC-feasibility scope.

Timing and cleanliness remain blocked.  Setup WNS changes from -0.31 to
-0.33 ns and TNS from -7,318.06 to -7,891.18 ns, although violating paths
fall from 34,814 to 31,458.  Post-compile warning records fall from 56,677 to
44,513, dominated by the removed M2 full-binding `LINT-28` surface, but the
remaining typed-carrier/feedthrough/shorted-output warnings and two high-
fanout nets are not structurally clean.  The disposition is therefore
`tool_input_pass + mapped_area_improved + timing_blocked +
structural_cleanliness_blocked`, never PPA or net-benefit evidence.

### M2/P3 wrapper P0 control-realization diagnosis (2026-11-03)

The read-only successor diagnosis is recorded in
[`dc_m2_p3_wrapper_p0_diagnosis_20261103.md`](dc_m2_p3_wrapper_p0_diagnosis_20261103.md).
It queries only the accepted refined DDC/native reports and current generated
HDL/source; it changes no RTL and launches no synthesis.

The wrapper owns 2,968,610.1130 cell area, 75.1% of the refined Route-A total.
Its two `36 x 64` membership record tables account for 956,160 of 990,322 raw
state bits and 442,368 of 476,140 mapped sequential cells.  DC has already
pruned most duplicated source fields, so merging full bundles alone is not a
mapped-area result.

The first bounded candidate is an internal 79-bit member record plus 80-bit
pending-read suffix.  Bank/index and already validated stage headers recover
layer, head, group fields and ordinal; `entry_id` is recovered from the frozen
coordinate equation only at its consumers.  Pre-DC accounting predicts a
589,824-bit raw reduction but only a 76,032-cell mapped-sequential ceiling,
which is the meaningful next native-DC question.  The persistent
reconciliation journal remains intact.

The later independent candidates are an equivalent hierarchical materializer
selector and an ordinal-indexed full-equality reconciliation lookup.  Eighteen
of the 20 native setup paths explicitly start or end in `m2P3`, principally at
`materializedMembers` or `stageState`, so selection logic is timing-relevant.
No P1 RTL, generated successor or new DC run has started.  Each candidate must
close its own functional/generation gates and commit before any separately
authorized same-fair-v1 tmux run.

### M2/P3 compact-membership functional batch (2026-11-03)

The first P0 candidate is now implemented and functionally accepted in
[`dc_m2_p3_wrapper_compact_membership_implementation_20261103.md`](dc_m2_p3_wrapper_compact_membership_implementation_20261103.md).
The wrapper retains only the 79-bit member record and 80-bit pending suffix;
stage/index-owned coordinates and headers reconstruct the public observation,
while the reconciliation journal remains intact.

The final remote clean regression is 57/57 across 14 suites, with outer
`KVZAP_COMPACT_MEMBERSHIP_P1_FULL_REGRESSION_EXIT=0` and no aborted suite.
The stale integration witness found during the first run was repaired without
changing production control: it now follows the real admission/P3 handshakes
and R3-owned M2 request/response ordering.  This closes only the functional
batch.  A new immutable 48-file successor, source/port/owner/state checks and
five paired proxies are still required before any separately authorized DC
comparison.

The successor/proxy gate is now closed by
[`dc_m2_p3_wrapper_compact_membership_successor_20261103.md`](dc_m2_p3_wrapper_compact_membership_successor_20261103.md).
The immutable 48-file root is `m2p3_compact_7bcd652_p9`; 16/16 typed ports,
12/12 production owners, four raw Route-A array interiors and five paired
same-header proxies pass.  The wrapper raw generated state is exactly 400,498
bits versus 990,322 in the prior accepted successor, a 589,824-bit reduction.
The paired archive SHA-256 is
`61d4e51cafea3c96167f371c41b31af051ca5844fd93f58ccba127b681cf7008`.
This is source/proxy evidence only.  No mapped area, clock load, lint or timing
result follows, and no same-fair-v1 DC run has been launched.

The user subsequently authorized the separately frozen paired run recorded in
[`dc_m2_p3_wrapper_compact_membership_dc_run_20261103.md`](dc_m2_p3_wrapper_compact_membership_dc_run_20261103.md).
Static fair-v1 coverage passed and
`dc_feasibility_fair_m2p3_compact_20261103_r1` is active in tmux
`kvzap-control-refine:p10-compact-dc`.  It uses the unchanged 2.0-ns profile,
the same Full-KV input, library, constraints and five proxy boundaries.  No
result marker exists at launch; await user notification and then inspect both
side exits, paired/outer markers, copied hashes and all native reports.

## Current new-conversation prompt

RD1 is implemented as a bounded candidate; see
[`dc_rd1_member_read_sharing_implementation_20261104.md`](dc_rd1_member_read_sharing_implementation_20261104.md).
The per-bank M/S/O member-record helper passes the 6,912-address local
equivalence miter, compiles, and passes the existing 9/9 focused wrapper
materialization/publication tests. Isolated original/shared read-network
synthesis run `rd1_read_network_screen_20261104_r1` completed with all exit/PASS
markers and native artifacts. Under identical fair-v1 screen constraints,
combinational area falls 342,379.460369 -> 126,874.772938 (-62.943%), while
worst path arrival rises 0.578519 -> 0.634739 ns (+0.056220 ns); both retain
positive slack, zero TNS and zero violating paths. This accepts RD1 as an
isolated area-positive candidate with a small local delay cost. Whole-wrapper
integration acceptance remains pending.
No new complete DC run is launched, and the active entry_id repair inputs
and process are untouched.

The next independent read-only P0 is complete for Page Manager; see
[`dc_page_manager_p0_diagnosis_20261104.md`](dc_page_manager_p0_diagnosis_20261104.md)
and its state CSV. Page Manager is 407,440.9906 area (11.242% of Route-A).
The 36,720-bit `allocatedLine` state plus its `reclaimLine` selection cone is
the dominant target: 92,555.232 sequential area and an 85,193.304 directed
combinational cone; the native path is a global-WNS path at -0.31 ns. PM1
selects an exact-lowest, same-cycle balanced/banked selector screen while
retaining all bits and parent control. PM2 separately derives stored
layer/head from the 288-slot coordinate and directly indexes payload-durable
validation. P0 changes no RTL and launches no compile or complete DC.

The user-authorized PM1 isolated candidate is implemented and locally
verified; see
[`dc_pm1_exact_priority_selector_implementation_20261104.md`](dc_pm1_exact_priority_selector_implementation_20261104.md).
It retains all 36,720 line bits and exact lowest-index/current-cycle behavior,
using 574 fixed 64-entry banks with a zero-padded final bank. A 13-bit
partial-bank miter passes all 8,192 vectors; full geometry passes zero/all-one,
all 36,720 one-hot choices, selected bank/tail boundaries and 1,024 random
dense/sparse patterns. Production Page Manager is unchanged. Two isolated SV
tops are frozen for same-fair-v1 small synthesis, but generated source size is
not mapped-area evidence. The isolated run
`pm1_selector_screen_20261104_r1` from source commit `8aa2031` failed in native
DC Pass-1 mapping of the original side with `SIGSEGV` and outer exit 139.
Analyze, elaborate, link, library loading, fair-v1 constraint application and
all input/hash checks passed first. No side PASS, DDC, mapped HDL, area or
timing report exists, and the banked candidate was never attempted. The failed
root is preserved and the tmux window/process are gone. Do not repeat the
identical harness; first prepare a matched, mapping-robust successor screen.

That mapping-robust successor is now locally prepared; see
[`dc_pm1_registered_selector_successor_20261104.md`](dc_pm1_registered_selector_successor_20261104.md).
It leaves both r1 selector bodies byte-identical, adds the same 36,720-bit Q
state and 17-bit D result registers to both sides, and runs each side in a
separate DC process. A bounded registered miter passes 1/1 across 1,344 shift
cycles and both full-width wrapped inputs pass Verilator lint. The matched
sequential boundary is not PM1 savings. No remote r2 result exists at this
checkpoint. The versioned r2 run was subsequently launched from commit
`9e6632b` in `kvzap-control-refine:p14-pm1-reg-r2` with run ID
`pm1_registered_selector_screen_20261104_r2`. Input closure passes and the
original side again segfaulted in Pass-1 mapping of the unchanged flat child
after analyze/link/constraint and the 36,737-register precompile gate; side
exit is 139. The isolated banked process completed with side PASS/exit zero and
native artifacts, but the combined run correctly ended FAIL/outer exit 1.
There is no matched area/timing comparison. Banked-only partial evidence is
66,640.727301 combinational area with precise setup slack +0.000505 ns; its 28
hold violations are on the artificial shift-state path. Preserve r2 and do not
repeat or relabel it as PM1 acceptance.

The compact-table read-port inventory and selected RD1 plan are recorded in
[`dc_compact_membership_read_sharing_plan_20261104.md`](dc_compact_membership_read_sharing_plan_20261104.md)
and its CSV companion.  Six member readers and two suffix readers are
identified.  M/S/O requests are mutually exclusive within one bank, while
global serialization is not assumed.  RD1 selects per-bank sharing of only
their 79-bit member read; C/F/B validation and 80-bit suffix reads remain
independent.  Production M->C equality and S->B exclusive wiring do not justify
removing generic wrapper checks. That earlier batch was audit/plan only;
the RD1 candidate implementation is tracked separately above.

A read-only mapped attribution of the completed compact wrapper is recorded in
[`dc_compact_wrapper_hotspot_attribution_20261104.md`](dc_compact_wrapper_hotspot_attribution_20261104.md).
The two membership tables retain exactly 366,336 sequential cells and about
1,292,433 area (49.0% of the whole wrapper).  Direct primitive read/association
cones have a deduplicated lower-bound area of 774,659 (64.4% of direct
combinational area).  Materialized work alone is only an 11.8%-of-wrapper
lower-bound cone, not the complete area explanation.  This supports targeted
record-read/decode optimization and a separately accounted storage study,
without changing capacity, concurrency or semantics.  The ongoing driver
repair run and its inputs remain untouched; no new optimization was implemented.

The entry_id structural regression is now isolated and a synthesis-only repair
is implemented; see
[`dc_entry_id_driver_repair_20261104.md`](dc_entry_id_driver_repair_20261104.md).
Focused DC positive/negative controls and 5,536 mapped functional vectors pass.
The explicit policy preserves only the shared 24-bit result and rejects any
of its 48 output bits without a driver.  No RTL, interface or numerical fair-v1
constraint changes were made.  Production paired-DC verification is still
required before this repair can be declared fully closed; no further control
optimization is in progress.

The production repair verification is active as
`dc_feasibility_fair_m2p3_entryid_repair_20261104_r1` in tmux
`kvzap-control-refine:p11-entryid-dc`; total log is
`entryid_repair_p11_dc_20261104.log`.  The implementation commit is `2c40d80`.
Static preflight passed and Full-KV entered native DC.  Await user notification,
then inspect the new driver gate plus all paired completion/provenance/native
reports.  No production repair completion is claimed at launch.

The production repair run has now completed and supersedes that launch-only
status; see
[`dc_m2p3_entry_id_repair_result_20261105.md`](dc_m2p3_entry_id_repair_result_20261105.md).
Both tops exit zero, RUN_PASS/outer exit pass, and the 48-bit gate reports
real startpoints for every entry_id output with zero LINT-3/LINT-5. Relative
to the first refinement, accepted compact membership reduces Route-A cell area
8.362% and sequential cells exactly 76,032; total area is 3,622,375.558791,
or 156.871x Full-KV. Timing remains blocked at WNS -0.31 ns, TNS -8,577.41 ns
and 35,897 violating paths. The specific driver regression is closed, but
44,533 warnings and high fanout keep broad cleanliness blocked.

RD1 now has a complete immutable generated-input freeze; see
[`dc_rd1_full_input_freeze_20261105.md`](dc_rd1_full_input_freeze_20261105.md).
The remote root `rd1_shared_e5d3107_p15` records source commit `e5d3107`, 48
unique Route-A filelist entries, byte-identical Full-KV HDL, unchanged compact
raw state and 5/5 proxy closure.  Its paired archive SHA-256 is
`9494f1dc4b47f1bfbcffe655b75e20a0d4c9cd75fb9802b5d454f870ae02dc5b`.
The accepted entry_id preservation policy remains enabled.  This is an input
freeze only; no complete RD1 mapped-area or timing result exists yet.

The complete RD1 paired DC has finished and been inspected; see
[`dc_rd1_full_paired_dc_result_20261106.md`](dc_rd1_full_paired_dc_result_20261106.md).
Both native exits, RUN_PASS, outer exit, hashes and required artifacts pass.
Full-KV reproduces its immutable metrics.  Route-A area is 3,388,597.345862,
6.454% below accepted compact/entry-id and 146.747x Full-KV; wrapper area falls
9.502%.  Setup worsens to WNS -0.36 ns, TNS -9,774.02 ns and 35,959 violating
paths.  Sequential cells remain 577,106; clock load remains unchanged.
All 48 entry-id bits have real drivers, with zero LINT-3/LINT-5, but total
warnings rise three to 44,536.  Tool/input and mapped-area gates pass; timing
and broad cleanliness do not.  The old p16 pane is absent and no RD1 process
remains; reports/logs are authoritative.  PM1 and RD2 are not in this run.

PM1 has a new production-module integration candidate, isolated from the
frozen RD1 run; see
[`dc_pm1_page_manager_integration_20261105.md`](dc_pm1_page_manager_integration_20261105.md).
`RouteAPageManager` retains the legacy selector by default and exposes one
explicit candidate-only realization flag.  The real Page Manager with PM1
enabled passes 5/5 reclaim tests.  No mapped comparison is claimed; the next
gate is a read-only saved-DDC replacement-readiness probe rather than another
flat-selector synthesis rerun.

The read-only saved-DDC readiness gate now passes; see
[`dc_pm1_saved_ddc_replacement_readiness_20261105.md`](dc_pm1_saved_ddc_replacement_readiness_20261105.md).
The accepted mapped top retains exactly one hierarchical
`route_a_page_manager` design/instance with 4,289 boundary pins, all 36,720
allocated-line registers and the 135,331-cell selector fanin boundary.  This
authorizes preparation of a characterized bottom-up PM1 child-replacement
screen, not a mapped-benefit claim or full-top acceptance.

The selected controlled screen is specified in
[`dc_pm1_characterized_replacement_plan_20261105.md`](dc_pm1_characterized_replacement_plan_20261105.md).
It emits a port-identical full-profile `route_a_page_manager_pm1`, relinks only
the unique saved-DDC child, characterizes the real top environment and maps
only the candidate child.  Preparation compile and PM1 reclaim tests pass
5/5.  This remains a provisional bottom-up screen pending candidate input
generation and later full-top confirmation.

Candidate-child generation was launched with byte-identical inputs in
`kvzap-control-refine:p18-pm1-child-freeze` and has ended at the intended
port-identity gate; see
[`dc_pm1_page_manager_successor_generation_result_20261105.md`](dc_pm1_page_manager_successor_generation_result_20261105.md).
CHIRRTL and split RTL generation succeeded, but the standalone emitter exposed
74 fields that the real parent context removes: 218 candidate ports versus 144
frozen child ports, with no frozen port missing.  The outer exit is 1, hash and
success markers were not produced, and no DC ran.  Reject p18 as a replacement
input.  The next attempt must generate PM1 under the same real measurement
parent and compare the contextually lowered child; do not force relinking or
invent a pin map.  The separate RD1 paired DC remains active in
`kvzap-control-refine:p16-rd1-dc` and must not be disturbed.

The contextual-generation repair is implemented and locally closed; see
[`dc_pm1_contextual_generation_fix_20261105.md`](dc_pm1_contextual_generation_fix_20261105.md).
The Page Manager selector flag remains default-off in the real measurement
parent, while the PM1-only emitter now elaborates the complete parent with the
flag explicitly enabled.  Compile, contextual elaboration 1/1, PM1 reclaim
5/5, script syntax and diff checks pass.  A new remote generation must still
prove exact post-firtool child-port identity before replacement DC is allowed.

The remote contextual generation has completed successfully; see
[`dc_pm1_contextual_generation_result_20261105.md`](dc_pm1_contextual_generation_result_20261105.md).
Inputs are frozen at `6dc1671`; p19 exits zero with both identity/success
markers, 48 split files, exact 144-to-144 child-port identity and fully
rechecked hashes.  The PM1 child is now an accepted input for the planned
characterized saved-DDC replacement screen.  No DC ran and no mapped-area or
timing conclusion follows.  RD1 DC remained independently active in
`p16-rd1-dc` at inspection time.

The characterized replacement runner and Tcl are now implemented and
statically checked; see
[`dc_pm1_characterized_replacement_implementation_20261105.md`](dc_pm1_characterized_replacement_implementation_20261105.md).
They pin the accepted DDC and p19 child hashes, use fail-closed compatible
relinking, characterize timing/constraints/connections, compile only the PM1
child, and require 62,000 registers plus the R5 proxy before and after mapping.
The accepted top is not recompiled.

The first characterized replacement screen has failed before candidate
elaboration completed; see
[`dc_pm1_characterized_replacement_result_20261105.md`](dc_pm1_characterized_replacement_result_20261105.md).
Its immutable input gate and baseline DDC/report stages pass, then DC reports
`VER-30` stack overflow at the 146,880-bit release reduction and exits 139.
The runner inherited an 8,192 KiB stack, unlike the accepted full DC runner's
unlimited-stack guard.  No relink, characterization, candidate compile, area or
timing result exists.  Preserve r1; the bounded successor is a new-root rerun
with only the established unlimited-stack guard added.  RD1 DC remained active
in `p16-rd1-dc` at inspection time.

The bounded r2 correction now adds a fail-closed unlimited-stack guard before
`dc_shell`.  All RTL, DDC, candidate, library, constraint, relink,
characterization, 62,000-register and proxy gates remain unchanged.  r1 is
preserved and must not be overwritten.

The unchanged-input r2 screen has completed with a new fail-closed gate; see
[`dc_pm1_characterized_replacement_r2_result_20261105.md`](dc_pm1_characterized_replacement_r2_result_20261105.md).
Unlimited stack resolves r1: candidate Presto analysis, elaboration and link
all complete.  The unmapped candidate then reports 62,002 registers against
the 62,000 mapped-baseline expectation, so r2 exits 1 before relinking,
characterization or compile.  This is not proof of added PM1 state because the
selector helper is combinational and the two counts are from different
realization stages.  Do not relax the gate before measuring the legacy raw
child under the same precompile path or identifying the exact two optimized
bits.  RD1 DC remained active in `p16-rd1-dc` at inspection time.

Source-level state extraction now proves the frozen legacy and PM1 children
have identical register declarations, widths and nonblocking targets: 628,917
objects and 1,678,810 raw bits on both sides, with no additions, removals or
width changes.  The bounded same-layer DC diagnosis is specified in
[`dc_pm1_legacy_precompile_count_probe_20261105.md`](dc_pm1_legacy_precompile_count_probe_20261105.md).
It uniquely renames the frozen legacy module, performs only unlimited-stack
analyze/elaborate/link, and requires 62,002 precompile registers plus one R5
proxy.  Do not change the replacement gate until this probe passes.

The same-layer legacy count probe has completed successfully; see
[`dc_pm1_legacy_precompile_count_result_20261105.md`](dc_pm1_legacy_precompile_count_result_20261105.md).
Run `pm1_legacy_precompile_count_20261105_r1` reports exactly 62,002 legacy
precompile registers, one R5 proxy, native PASS and both outer exits zero.
All frozen input hashes recompute exactly.  Together with the PM1 r2 candidate
count, this proves that both raw children have 62,002 precompile registers;
the accepted 62,000 figure is postcompile.  The r2 failure was therefore a
mixed-stage gate rather than PM1-added state.  Repair the main screen with
separate 62,002 precompile and 62,000 postcompile expectations before rerun.
The joined PM1 pane closed cleanly; the surviving RD1 pane remained live and
was relabeled back to `p16-rd1-dc` without interrupting DC.

The replacement screen's mixed-stage gate is repaired for r3; see
[`dc_pm1_characterized_replacement_r3_repair_20261105.md`](dc_pm1_characterized_replacement_r3_repair_20261105.md).
It now requires 62,002 registers before candidate compile and 62,000 cells for
both accepted and candidate postcompile checks.  No RTL, candidate input,
port/relink policy, characterization, clock, constraint, proxy or compile
effort changes.  This repair alone is not a synthesis result.

The repaired characterized replacement r3 run has completed with qualified
diagnostic evidence; see
[`dc_pm1_characterized_replacement_r3_result_20261106.md`](dc_pm1_characterized_replacement_r3_result_20261106.md).
Inputs, stack, 62,002/62,000 stage counts, DDC, mapped HDL and all native
reports close.  PM1 reduces child cell area 4.201% and relinked-top area 0.473%,
with unchanged setup WNS -0.31 ns and modest TNS/path-count improvement.
However, it introduces one -0.005321-ns hold path, four net lint warnings and
one additional top high-fanout net.  Two stale collection handles produce
terminal `SEL-001` errors and blank baseline-register/proxy summary cells even
though the script prints PASS/exit zero.  Clean screen acceptance is withheld;
snapshot scalar counts and add explicit error/summary completeness closure
before deciding on a short saved-DDC validation or clean replay.  RD1 remained
live and advancing in `p16-rd1-dc` at the 2026-11-06 inspection snapshot.

The stale-collection and false-PASS mechanism is now repaired in source; see
[`dc_pm1_stale_collection_gate_repair_20261106.md`](dc_pm1_stale_collection_gate_repair_20261106.md).
The Tcl snapshots scalar counts before relink, and the runner now requires all
artifacts, an error-free native log and an exact non-empty summary before exit
zero.  No RTL or synthesis method changes.  This repair has static closure
only; validate the existing r3 mapped DDC through the separately bounded short
saved-DDC path before considering a clean full replacement replay.

The saved-DDC-only short validator is implemented and statically closed; see
[`dc_pm1_saved_ddc_validation_implementation_20261106.md`](dc_pm1_saved_ddc_validation_implementation_20261106.md).
It reuses the accepted top DDC and r3 mapped PM1 DDC, performs fail-closed
relink and reporting, and validates scalar counts, area, timing and lint.  It
cannot analyze, characterize, compile or overwrite mapped artifacts.  Launch
it in a fresh result root before considering any 3.3-hour clean replay.

The saved-DDC-only validation has completed successfully; see
[`dc_pm1_saved_ddc_validation_result_20261106.md`](dc_pm1_saved_ddc_validation_result_20261106.md).
Native PASS, postcheck PASS and both exit-zero markers close with no native
error, complete scalar summary and exact r3 area/timing/lint reproduction in
about 9.7 CPU minutes.  This closes PM1 at its bottom-up diagnostic tier:
4.201% Page Manager area and 0.473% relinked-top area reduction, unchanged
setup WNS, one small hold regression and four additional lint warnings.  No
repeat 3.3-hour screen is needed solely for the stale summary.  Complete
integrated same-fair-v1 successor DC remains a later production-acceptance
gate.  RD1 remained live and untouched in `p16-rd1-dc`.

The two failed standalone PM1 screens were removed from the formal remote
`runs/` namespace and retained under the recoverable failure archive described
in [`dc_output_cleanup_20261105.md`](dc_output_cleanup_20261105.md).  No active,
accepted or older successful output was moved.  This was namespace cleanup
only and did not reclaim disk capacity.

The compact-membership DC run has completed.  The current result authority is
[`dc_m2_p3_wrapper_compact_membership_result_20261104.md`](dc_m2_p3_wrapper_compact_membership_result_20261104.md).
Both side exits, paired/outer markers, hashes and native artifacts pass.
Observed Route-A area falls a further 8.313% to 3,624,318.814461 and sequential
cells fall exactly 76,032 to 577,106.  Full-KV reproduces the prior result.
Setup remains blocked: WNS -0.31 ns, TNS -8,564.11 ns and 35,671 violating
paths.  New LINT-3/LINT-5 warnings identify 24 undriven entry_id nets and 48
undriven wrapper output bits after synthesis deletes the reconstruction cone.
Raw HDL still drives the fields; current production consumers do not use
entry_id.  This is a structural regression requiring bounded diagnosis before
accepting a fully closed successor or launching another optimization/rerun.
The warning total is 44,585.  Preserve the run and all constraints; no PPA or
system-benefit claim follows.

The active-run prompt in
[`dc_control_refinement_active_run_handoff_20261102.md`](dc_control_refinement_active_run_handoff_20261102.md)
is retained as a historical snapshot.  Use the accepted result above for any
successor discussion; no additional refinement or DC run is automatically
authorized.

The next structure-opportunity review is
[`dc_next_structure_opportunities_20261106.md`](dc_next_structure_opportunities_20261106.md).
It prioritizes remaining wrapper record readers and materializer selection,
with independent ordinal-indexed reconciliation and M2 slot-search P0 work.
It distinguishes measured predecessor costs from unmeasured candidates and
identifies the retained 366,336-bit compact-table storage as a major cost
requiring separate realization study for larger state savings.  No RTL or
experiment is started by this documentation-only review.

RD2 has an isolated candidate while frozen RD1 DC continues; see
[`dc_rd2_decoded_read_implementation_20261106.md`](dc_rd2_decoded_read_implementation_20261106.md).
It keeps the RD1 reader on both screen sides and compares explicit decode
against nested indexing for the remaining C/F/B and M/C suffix readers.
Production wrapper, lifecycle, storage and frozen RD1 input remain unchanged.
Local differential verification and immutable screen-input emission precede
any remote small-synthesis launch; integration requires separate closure of
out-of-range/ready behavior and complete functional/source checks.
The local r4 verification/emission run has failed its completion gate; see
[`dc_rd2_local_validation_r4_result_20261106.md`](dc_rd2_local_validation_r4_result_20261106.md).
The log `/tmp/kvzap_rd2_local_20261106_r4.log` ends with outer exit 143;
the kernel records a new `cc1plus` OOM kill during 36 x 64 simulator build.
Verilator merged split sources into two fast C++ translation units, so the
split-output/two-job settings did not sufficiently bound optimizer memory.
No complete two-test PASS, paired emitter or RD2 DC input exists.  The local
tmux shell remains available; no validation process or remote RD2 DC is live.
Repair simulator grouping/build settings, preserve geometry and stimulus,
then require a new full functional/emitter closure before small synthesis.
The next successor moves those checks to an isolated EDA-server source
snapshot; see
[`dc_rd2_remote_validation_migration_20261106.md`](dc_rd2_remote_validation_migration_20261106.md).
C++ build jobs are limited to one with two Verilation jobs; the helper,
stimulus and full geometry are unchanged.  Source hashing, two-case XML test
acceptance and exact paired-port/output-hash checks precede any RD2 DC.
The first remote p25 attempt stopped before JVM startup because the installed
Java 21 binary requires a newer glibc.  Its artifacts/log remain preserved.
Use the proven native Java 11 runtime, as in accepted p19, and a new root for
the retry.  This environment failure provides no RD2 test or synthesis result.
The corrected remote run has completed successfully; see
[`dc_rd2_remote_validation_result_20261106.md`](dc_rd2_remote_validation_result_20261106.md).
The two-case suite passes at 4 x 8 and 36 x 64, paired RTL emission and
postcheck pass, and both exits are zero.  All 133 source hashes, both emitted
SV hashes and exact paired port headers independently recheck.  The accepted
inputs remain under `artifacts/rd2_remote_validation_48f8cf3_p26_r2` on the EDA
server.  RD2 has no mapped result yet; freeze these inputs for an independent
small-synthesis comparison before production integration.  RD1 has also
completed and is recorded separately above.  No KVZap test/DC process remains
active at this snapshot; no new synthesis is launched by the inspection.
The next authorized RD2 isolated screen input is frozen; see
[`dc_rd2_read_screen_input_freeze_20261106.md`](dc_rd2_read_screen_input_freeze_20261106.md).
Its two RTL hashes, paired ports, test XML, five source snapshots and copied
fair-v1 scripts pass preflight under a new remote run root.  Both sides retain
RD1 and measure only the RD2 increment.  RD1+PM1 full paired DC remains
required for eventual integrated acceptance; defer the cumulative-input
choice until RD2's small-screen disposition.  No full-top DC is started here.
The RD2 isolated small-synthesis launch snapshot is recorded in
[`dc_rd2_read_screen_launch_20261106.md`](dc_rd2_read_screen_launch_20261106.md).
Run `rd2_read_network_screen_20261106_r1` has now completed in independent
tmux `kvzap-control-refine:p27-rd2-read-dc`; see
[`dc_rd2_read_screen_result_20261106.md`](dc_rd2_read_screen_result_20261106.md)
and JSON. Both native exits/PASS, postcheck/total PASS and outer exit 0 close;
15 frozen files, five source snapshots, accepted archive/library, test XML
and paired ports independently recheck. The valid screen is a negative area
result: 689,972.294920 -> 692,068.096534 (+0.30375%). Non-buffer/inverter
area saves 60,167.685683, but buffer/inverter area adds 62,263.487297;
inverters rise from 205 to 171,761, mostly on table input bits. Precision
setup slack is +1.046292 -> +1.026872 ns; hold +0.38 ns and TNS/counts 0
on both. Critical setup endpoints are common RD1 M/S/O outputs, not a
per-modified-reader timing diagnosis. Zero registers and identical 34 harness
lint warnings remain. Do not integrate current RD2 as an accepted area
optimization or update full-top results. Production out-of-range/ready
equivalence remains open; RD1+PM1 full paired DC is not started here.

The compact-table STORE P0 source/contract audit is complete; see
[`dc_compact_store_p0_audit_20261106.md`](dc_compact_store_p0_audit_20261106.md),
its field CSV and source-evidence JSON. Neither opaque 64-bit field has a
proven shorter value encoding. A concrete next candidate is reuse of the
existing R3 journal's immutable suffix fields, avoiding duplicate storage
rather than discarding information. Production enforces one <=64-member,
single-layer group per reset; generic unbound packing still supports the
36 x 64 member capacity. The journal's global ordinal nonreuse is an assertion,
not an admission ready gate, so a 64-slot replacement is not automatically
equivalent at the generic boundary. Member values survive publication until
post-commit observations; journal values persist until reset. ST1 needs a
separately scoped equivalence-domain/proof plan before implementation. This
documentation-only batch changes no RTL and performs no remote access, test
build or synthesis; RD2 remains untouched and no completion check is made.

ST1's equivalence-domain and verification plan is now recorded in
[`dc_st1_journal_suffix_equivalence_plan_20261106.md`](dc_st1_journal_suffix_equivalence_plan_20261106.md),
with 30 planned cases and source/abstract-check evidence. Reusing journal
suffix fields has a conditional generic storage relation under global bound-
ordinal nonreuse, while preserving two independent combinational M/C readers,
all continuous ready/valid behavior and the full unbound member capacity.
The original wrapper does not ready-gate cross-bank journal collisions; a
raw-history counterexample prevents unconditional generic equivalence. Do
not turn that DUT assertion into an unproved environment assumption. The
unqualified generic scope gate remains open before implementation. Sixteen
source checks and a reduced storage-equation enumeration pass; neither is
RTL equivalence. No candidate RTL or test harness is added, no remote access
is performed and all planned RTL/DC cases remain NOT_RUN. RD2 is untouched.

ST1's next scope/key-validation batch is complete; see
[`dc_st1_scope_key_validation_result_20261106.md`](dc_st1_scope_key_validation_result_20261106.md)
and its result JSON. The reviewed contracts establish ordinal identity within
a group and the production ingress's one-group-per-reset journal bound, but
not a global ordinal-nonreuse obligation for every generic caller. Nineteen
actual source expressions were replayed over 14 check groups, including the
expected cross-bank assertion violation and a separately marked overwrite
diagnostic. Four checker/mutation regressions pass. This is source-predicate
evidence, not HDL simulation or wrapper equivalence. Keep the existing generic
suffix backing: the simple journal-only variant is not eligible under the
current unqualified compatibility requirement. No new input assumption or
ready gate is approved. Full-wrapper RTL/DC cases remain NOT_RUN. Production
and testbench RTL, frozen inputs and RD2 are unchanged; no remote access or
synthesis occurred. Conditional production reuse remains an unimplemented,
separately scoped choice rather than a generic pass.

The generic wrapper remains unchanged while storage alternatives are analyzed;
see [`dc_compact_storage_realization_options_20261106.md`](dc_compact_storage_realization_options_20261106.md)
and its evidence JSON. Read-only library/native-report inspection confirms
sampled table bits use integrated-enable EDF cells. The concrete next
per-bit-cost candidate is WCG1: ordinary DFFs with shared, characterized word
clock gates and separate 79/80-bit enables. Its 369,267-area gross scalar-cell
difference excludes every new gate/peripheral/timing cost and is NOT a mapped
saving. An asynchronous multi-read RF is the separately scoped larger
realization direction; the inspected 64 x 64 synchronous one-port SRAM is not
drop-in compatible. Reverse journal reuse retains generic data but can remove
only 5,120 suffix-copy bits before extra-read costs. No usable multi-bit DFF
is established by the companion-model scan. This batch changes documents
only, launches no EDA tool and reads no RD2 state; no candidate RTL or new
clock/constraint/macro selection is made.

WCG1's cost/edge feasibility assessment is complete; see
[`dc_wcg1_cost_edge_feasibility_20261106.md`](dc_wcg1_cost_edge_feasibility_20261106.md)
and its JSON. Native library-only probe r3 closes all markers/hashes and
prices the positive-clock gate at 2.520 area; bare 79/80 ordinary-DFF clock
pin loads fit its output cap limit without wire. The uniform-cell arithmetic
after 4,608 gates leaves 357,654.528 area before buffering/hold/resizing costs,
NOT mapped savings. Actual functional cell models pass 978 unit comparisons
and 552 logical gate-edge checks; three negative/diagnostic variants differ
as expected. Synthetic 50-ps gated capture demonstrates why native hold and
clock-propagation closure remain necessary, not a measured timing failure.
WCG1 needs no ST1 ordinal-nonreuse/capacity concession, but full generic RTL
integration and gated STA remain open. Probe r2's captured Library Compiler
report error is retained/rejected; r3 and four postcheck regressions close
that false-PASS mechanism. Production RTL/RD2 are unchanged; no design
synthesis or full paired DC ran. Next is a separately scoped matched mapping
and gated-clock timing screen, not immediate wrapper replacement.

WCG1 matched bank mapping/STA preparation is now verified; see
[`dc_wcg1_matched_bank_mapping_plan_20261106.md`](dc_wcg1_matched_bank_mapping_plan_20261106.md).
The scope is one complete 64-record bank, native EDFQD versus DFQD plus
128 CKLNQ gates, with identical registered launch boundaries, readers and
2-ns numerical constraints. Both sides propagate cell clocks and retain
raw as well as identical-policy hold-repaired snapshots. The 64-row cell
simulation passes 768 output comparisons; eight focused regressions pass.
Native preflight r2 verifies storage/gate/E-pin inventories and actual library
gating checks; preflight r1's pin-filter error is retained. Preparation itself
produces no mapped-area or mapped timing evidence. Production RTL and RD2
remain untouched. The frozen run `wcg1_bank_mapping_sta_20261106_r1` is now
completed both native sides in independent `kvzap-wcg1-map:paired-sta`, but
its Python summary failed and outer exit is 1; see
[`dc_wcg1_bank_mapping_launch_20261106.md`](dc_wcg1_bank_mapping_launch_20261106.md)
and its JSON for exact input hashes and launch paths. Current diagnosis is
[`dc_wcg1_bank_mapping_error_diagnosis_20261106.md`](dc_wcg1_bank_mapping_error_diagnosis_20261106.md)
and JSON: DC 2018's missing design `area` attribute produces empty scalar
metrics; native Total cell area is present. Both sides have native exit 0,
raw/repaired DDC and reports. Native repaired area reduction is 16.5262% in
the one-bank fixture; gated raw hold -17.9208 ps becomes +3.52895 ps after
repair, with setup +1.06405 ns unchanged. These are audited native observations,
not a completed postcheck acceptance or a top-level result. No restart or
tooling/RTL change was performed. Next is a versioned short postcheck repair
using existing native reports, preserving r1's failed marker and frozen inputs.
The short validator preparation is recorded in
[`dc_wcg1_saved_validation_preparation_20261106.md`](dc_wcg1_saved_validation_preparation_20261106.md):
native area/precision reports are authoritative, explicit pinned recovery
leaves source metrics unchanged, and 26 regressions plus ordinary-Tcl reader
checks cover the failure. The completed remote result is
[`dc_wcg1_saved_artifact_validation_result_20261106.md`](dc_wcg1_saved_artifact_validation_result_20261106.md)
and JSON: **ACCEPTED_MATCHED_BANK_SCREEN**, postcheck/run PASS and new outer
exit 0 in `kvzap-wcg1-map:saved-check`. No DC tool ran; all 78 original files
retain identical hashes and original r1 outer exit stays 1. Accepted repaired
one-bank cell area is 56,919.576720 versus 47,512.919348, saving 16.5262%.
Precision setup slack is +1.064047 ns for both, gated hold +0.003529 ns,
enable setup/hold +1.649341/+0.066130 ns, and repaired TNS/path counts are 0.
Raw gated hold failure is retained. The same 12 LINT-28 warnings remain on
each side. This accepts only the matched bank mapping/STA screen; production
wrapper integration, whole-top area/timing and physical hold signoff are open.
Do not update the full Route-A/Full-KV ratio or infer PPA/system/net benefit.

The user now authorizes parallel work: RD1+PM1 complete paired DC and WCG1
wrapper isolation, excluding RD2. Preparation and frozen-component composition
are recorded in
[`dc_rd1_pm1_parallel_launch_20261106.md`](dc_rd1_pm1_parallel_launch_20261106.md).
The 2-ns profile and accepted entry_id/proxy policy remain unchanged. Only
the accepted same-header PM1 contextual child replaces RD1's Page Manager;
47 other Route-A units and Full-KV remain identical. The new fail-closed
freeze/launch must finish source/state/proxy/hash gates before DC. WCG1 must
remain outside this frozen input and pass real-wrapper functional/edge gates
before any later cumulative WCG1 full DC. The completed freeze and actual
RD1+PM1 launch are now recorded in
[`dc_rd1_pm1_full_paired_launch_20261106.md`](dc_rd1_pm1_full_paired_launch_20261106.md)
and JSON: archive `0f21d81d...`, all static/state/proxy gates pass, Full-KV
mapping started in `kvzap-rd1-pm1:paired-dc`; await user completion notice.
The WCG1 default-off implementation and real-wrapper differential validation
preparation are separate in
[`dc_wcg1_wrapper_isolation_20261106.md`](dc_wcg1_wrapper_isolation_20261106.md).
Bounded Scala compile and two 240-check native-gate comparisons pass, but
the planned eight real-wrapper functional tests are not yet accepted. They
are now launched independently; see
[`dc_wcg1_wrapper_functional_launch_20261106.md`](dc_wcg1_wrapper_functional_launch_20261106.md)
and JSON. `kvzap-wcg1-wrapper:functional` uses frozen commit `82bd953`,
122 sources excluding RD2, native Java 11 and serial C++ build. Remote Test
compile passes. The WCG1 job has now ended with outer exit 1; see
[`dc_wcg1_wrapper_functional_result_20261106.md`](dc_wcg1_wrapper_functional_result_20261106.md)
and JSON. Baseline passes 4/4; candidate fails 4/4 during Verilator simulator
construction because the simulation gate's nonblocking latch assignment
triggers fatal COMBDLY. Candidate stimulus/equivalence assertions did not run;
all 122 source hashes, archive/runner pins and XML reports recheck. This is
not eight-test acceptance or a new DC/timing result. Preserve r1; first repair
and preflight the simulation model/native-edge equivalence, then use a new
immutable functional retry. This inspection makes no code change or restart
and does not access the independent RD1+PM1 run. The earlier single-bank WCG1
mapped result remains separate; full wrapper timing/functional closure is open.
The authorized repair is now prepared in
[`dc_wcg1_wrapper_model_repair_20261106.md`](dc_wcg1_wrapper_model_repair_20261106.md)
and JSON. Only the simulation latch assignment changes; native binding,
wrapper protocol and eight tests are unchanged. Matching Verilator 5.041
reproduces old COMBDLY, builds the fixed executable without suppressions,
passes 6,156 capture/edge checkpoints and both negative controls. Two native
Icarus modes each pass 368 gate comparisons including root-edge NBA changes.
The runner now requires this preflight before any long retry. A new remote
eight-test run is now launched; see
[`dc_wcg1_wrapper_retry_launch_20261106.md`](dc_wcg1_wrapper_retry_launch_20261106.md)
and JSON. Frozen `844e586` retry uses `kvzap-wcg1-wrapper-r2:functional`,
archive `6565f23e...`, unchanged 122 project files except the model assignment,
and four pinned auxiliary preflight sources. Remote matching-Verilator
minimal build/capture/negative gates pass before sbt startup. Eight-test
functional completion is pending; await user notice. r1 remains failed and
unchanged, RD2 excluded, RD1+PM1 not accessed or modified. Do not infer
wrapper functional/timing acceptance from preflight or start a combined DC.

The r2 run is now independently accepted at **directed wrapper functional**
scope; see
[`dc_wcg1_wrapper_retry_result_20261106.md`](dc_wcg1_wrapper_retry_result_20261106.md)
and JSON. Baseline 4/4 and candidate/reference-miter 4/4 pass, all source/archive/
runner/preflight/XML hashes match, and postcheck/RUN_PASS/outer exit 0 plus
persisted exit_status=0 close completion. Four actual candidate binaries include
the repaired gate and the assertion layer (72 differential message sites per
case, --assert enabled). Four nonfatal VerbatimBlackBoxAnno warnings remain.
This supersedes r2's pending functional state only, preserving r1 failure and
all launch snapshots. No full-wrapper mapped area, native 2-ns STA, universal
equivalence or production integration is accepted. Next is isolated generated
input/native-binding closure and matched wrapper mapping/STA; no job is started.
RD1+PM1's running full synthesis is not accessed or changed in this audit.

The user separately authorizes the next isolated mapping/STA tier. Preparation
is in
[`dc_wcg1_wrapper_mapping_plan_20261106.md`](dc_wcg1_wrapper_mapping_plan_20261106.md):
actual same-profile wrapper export, exact inline-resource closure and native
4,608-gate binding preflight before matched 2-ns propagated-clock mapping.
Both raw and equally hold-repaired areas/timing must be retained. Local 34
input/postcheck regressions pass. Preparation is not a launch/result; the
separate frozen launch record is authoritative for later execution. Neither
production RTL nor the independent RD1+PM1 run is changed.

The guarded chain is now launched in a new immutable root; see
[`dc_wcg1_wrapper_mapping_launch_20261106.md`](dc_wcg1_wrapper_mapping_launch_20261106.md)
and JSON. Run `wcg1_wrapper_mapping_sta_d860732_20261106_r1` uses independent
`kvzap-wcg1-wrapper-map:paired-sta`, archive `5531bc6a...` and exact versioned
runner. Initial hashes/resource/DB/profile gates, private Scala compile,
both RTL exports and static field/header/state/inline closure pass. Actual
native-binding preflight is active; mapping/STA results remain pending.
A fail-closed native-binding gate precedes both mappings.
The user is notified to await completion. RD1+PM1 is not accessed or changed.

The initial mapping chain stopped fail-closed at native preflight, outer exit
7, before either formal side mapped. See
[`dc_wcg1_wrapper_mapping_preflight_repair_20261106.md`](dc_wcg1_wrapper_mapping_preflight_repair_20261106.md):
DC 2018 requires `set_size_only -all_instances` on the shared inline module's
native leaf. Its false command status produced UID-192/UID-457 even though
native gates linked; the independent Error scan rejected the misleading
binding marker. The corrected command also checks return status. Installed
command-reference review and 36 local checks pass; a new immutable r2 launch
is required, leaving r1 and RD1+PM1 untouched. This is not an RTL/timing fault.

The corrected immutable r2 chain is now launched; see
[`dc_wcg1_wrapper_mapping_retry_launch_20261106.md`](dc_wcg1_wrapper_mapping_retry_launch_20261106.md)
and JSON. Run `wcg1_wrapper_mapping_sta_211f1e2_20261106_r2` uses
`kvzap-wcg1-wrapper-map-r2:paired-sta`, archive `aebd5a07...`; the package
differs from r1 only in the native-sizing Tcl command/status check. All old
Chisel/constraint/runner/postcheck files remain identical, and 36 local tests
pass. Paired export/static input closure now pass and native preflight is
active without observed native errors; its success is still pending and
must precede both formal mappings. Await
user completion notice; no native area/timing result or production integration
is accepted at launch. r1 and the running RD1+PM1 synthesis are untouched.

The WCG1 wrapper mapping r2 result is now independently audited; see
[`dc_wcg1_wrapper_mapping_retry_result_20261107.md`](dc_wcg1_wrapper_mapping_retry_result_20261107.md)
and JSON. Both native sides, four snapshots, postcheck/run markers and outer
exit/status close at zero; source/archive/library/prepared-input and all 73
native artifact hashes recheck. Exact inline and native binding close with
4,608 CKLNQ gates, TIEL-driven TE=0, characterized gating checks and actual
positive clock-gate capture arcs. All 366,336 table bits and 48 entry_id
drivers remain. Matched hold-pass area is 2,295,026.201759 reference versus
1,936,432.671921 candidate, a **15.624812% isolated-wrapper reduction**.
Both sides report setup/hold TNS 0 and zero violating paths at the unchanged
2 ns; candidate setup slack is **0.000000 ns**, global hold +0.029539 ns,
gate-enable setup/hold +0.740547/+0.211413 ns. Accept only the isolated DC
screen, with no positive setup-margin or physical hold claim. Native root
fanout falls 400,110 -> 38,382, but TIM-134 and downstream clocks remain.
Structural cleanliness stays open: both sides retain 5,729 lint warnings,
one P3 proxy information entry and 554 min-capacitance violations. No lint
or complete constraint-cleanliness benefit is claimed. The frozen summary's
LINT token counts include category headings; the new audit uses native
summary/detail counts without rewriting old reports. All 36 local checks
pass. No new tool job, RTL integration or RD1+PM1 inspection occurs; preserve
production defaults and RD2 exclusion. Do not update RD1's whole-top area
or ratio by subtracting this isolated saving. A cumulative freeze/full paired
DC remains a separately authorized next stage.

RD1+PM1 full paired DC has now been independently inspected after the user's
completion request; see
[`dc_rd1_pm1_full_paired_result_20261107.md`](dc_rd1_pm1_full_paired_result_20261107.md)
and JSON. This supersedes its launch-only state above. Both native exits,
RUN_PASS and outer exit 0 pass, frozen source/proxy/library/constraint hashes
recheck, Full-KV reproduces 23,091.432498, and all 48 entry_id bits are driven.
Route-A area is **3,358,045.877079**, down **0.901596%** from RD1, ratio
**145.424x**. Page Manager area drops 4.243364%, but complete-top setup
regresses to WNS **-0.44 ns**, TNS **-12,096.60 ns**, 35,976 violating paths.
Hold TNS/path counts remain zero; 577,106 sequential cells and 577,110 clock
loads remain. Lint warning lines increase five to 44,541 and cleanliness
stays open. Accept tool/input closure and the small area benefit only, with
the setup tradeoff retained. No new DC, RTL change or WCG1/RD2 composition
is performed; WCG1's isolated saving is not an additive whole-top result.

The authorized setup-regression diagnosis is prepared in
[`dc_rd1_pm1_setup_diagnosis_20261107.md`](dc_rd1_pm1_setup_diagnosis_20261107.md)
and JSON. Existing native top-20 reports show both external ready/request
remapping and six direct Page Manager allocatedLine-to-reclaimLine paths at
-0.44 ns. A purely external-remapping explanation is insufficient. Saved-DDC
read-only STA is prepared to compare all reclaim bits/common endpoints and
partition negative endpoint slacks before choosing a same-cycle PM1 repair
or an RD1-only WCG1 attribution baseline. No RTL repair, synthesis or final
WCG1 integration choice follows from these preliminary reports.

## Incremental storage/service cost P0 (2026-11-06)

The read-only ledger is
[`route_a_incremental_storage_cost_ledger_p0_20261106.md`](route_a_incremental_storage_cost_ledger_p0_20261106.md),
with CSV and source/hash evidence JSON. P3's 1,179,648-B payload and 18,432-B
local sidecar, current M2's 19,040-B nominal entry arrays, and their child
protocol/access logic are excluded from accepted RD1 DC area; real parent
control and compact tables remain included. M2's existing 0.52857872-mm²
public-CACTI proxy has different modeled words/provision/access assumptions
and cannot price the current lookup plus two Valid write lanes directly.
P3 cross-layer read/write overlap also needs an explicit physical mapping.
Old 312-KiB analytical M2 provision is separate from current entries and
logical credit/group state; do not add them blindly or infer a new runtime
FIFO requirement. The audit changes documentation only, runs four source
guards, and neither accesses nor changes RD1+PM1/WCG1 remote work. No new
area/physical-timing/PPA or net-benefit acceptance is established.

## P3 storage-mapping feasibility (2026-11-06)

Read
[`p3_staging_storage_mapping_feasibility_20261106.md`](p3_staging_storage_mapping_feasibility_20261106.md)
after the incremental ledger. Capacity remains 1,179,648-B payload plus
18,432-B local sidecar. Independent payload read/write and sidecar write,
unchanged response latency/holding and reset-retained bytes are required.
The new finite payload model supports a 1RW-plus-one-write-buffer hypothesis:
the no-consume/replace rule guarantees a drain edge after a conflict. The
principal two-address/binary-data check passes 160 states / 37,888 transitions;
three negative controls catch lost conflict writes, reset loss and live-Q
response corruption. This is abstract feasibility, not RTL or macro closure.
Unbuffered shared 1RW is insufficient; per-layer 1RW banking needs its parent
phase restriction proved. No RTL, macro selection, DC/STA/CACTI or remote
inspection occurs. Exact RTL equivalence, collision semantics, complete cost
and native 2-ns setup/hold remain open. RD1+PM1/WCG1 handoffs are unchanged.

## Superseded pre-DC prompt seed (historical)

> Work in `/home/wz/AI/kvpress` on branch `research/kvzap-latest`. Read
> `AGENTS.md`, `analysis/architecture_spec.md`,
> `analysis/route_a_current_handoff.md`,
> `analysis/rtl2_phase_contract.md`, and
> `analysis/rtl3_9_c4_d_functional_completion_review.md` before editing; use
> `analysis/route_a_document_map.md` to select any stage-local evidence.
> Current state is RTL3 functional-subsystem closure complete. SRP.0--SRP.1-R
> passed human partition review; SRP.2 source/toolchain eligibility, SRP.3
> realization-requirements decision planning, SRP.4 differential-cost evidence
> planning, and SRP.5 completion review are complete. MBR.0's candidate
> measurement-boundary BOM passed human review; MBR.1 and MBR.1-A passed
> external technical review with minor corrections and received user approval.
> The Full-KV legal-path audit originally found all three baseline path
> segments missing. W0 has completed its bounded dual-DUT functional scope,
> and MR-1A has completed the Route-A-hot plus Full-KV common lifecycle/status
> scope. MR-1B B2c is complete only for its approved single-record functional
> contour: reconciliation, qualified withdrawal, cancel/abort, and R6-owned
> fault have passed remote directed and W0/MR-1A structural regressions. The
> MR-2's bounded M2 production control and admission-to-metadata membership
> bridge, real `MetadataAppend` operands, grouped entry-data
> prepare/commit/abort, actual bounded production entry state, and the M2
> logical entry-array boundary are live in `RouteAMeasurementDut`. The
> fixture-only `RouteAM2EntryStorage` is still not production evidence. The
> R5 availability/generation array-only boundary is also functionally closed;
> both M2 and R5 remain logical boundaries only, and no
> result selects a macro, wrapper ports/latency, or physical realization. None
> selects
> a top or begins physical realization work.
> Read
> `analysis/synthesis_realization_partition.md` and
> `analysis/srp3_realization_requirements_decision_plan.md`, and
> `analysis/srp4_differential_cost_evidence_plan.md`, and
> `analysis/srp5_completion_review.md`, and
> `analysis/measurement_boundary_selection.md`, and
> `analysis/measurement_boundary_bom.json`, and
> `analysis/measurement_baseline_fairness_plan.md`, and
> `analysis/measurement_baseline_matrix.json`, and
> `analysis/measurement_realization_candidate_proposal.md`, and
> `analysis/measurement_realization_candidate_manifest.json`, and
> `analysis/full_kv_baseline_path_audit_20261016.md`, and
> `analysis/full_kv_baseline_path_audit_20261016.json`, and
> `analysis/synthesis_eligibility_manifest.json`, and
> `analysis/realization_preparation_wrapper_common_disposition.md`. The
> wrapper/common disposition is human-approved; the M2 parent adapter is
> functionally verified (remote owner 5/5, boundary 1/1, cross-stage 40/40),
> while R5 and P3 parent adapters are functionally verified and S2 wrapper RTL
> remains pending. Do not advance beyond approved wrapper
> RTL to realization choice, synthesis,
> physical realization, PPA, or cost evaluation without a later approval;
> do not reopen pruning/admission/page/scheduler/atomicity or introduce
> physical HBM/SRAM, numeric pipeline, timing, PPA, model/GPU, or new A4 DSE
> claims. Preserve frozen artifacts, run no-model preflight/tests first, update
> live navigation, and commit each completed modification batch with its
> source/scope.

The saved-DDC diagnostic `rd1_pm1_setup_diagnosis_20261107_r1` is now launched
in `kvzap-rd1-pm1-setup:saved-sta`; its immutable paths/source pins are in
`dc_rd1_pm1_setup_diagnosis_20261107.json`. It is read-only STA, not synthesis.
Await user completion notice before auditing endpoint/TNS coverage and making
the PM1 repair/WCG1 baseline decision. No automatic retry or full DC is queued.

The saved-DDC setup diagnostic r1 has now failed before reporting timing:
DC 2018 omits propagated_clock on a saved ideal clock, and an empty-value
boolean check aborts after RD1 link. RD1+PM1 never starts. See
`dc_rd1_pm1_setup_diagnosis_retry_20261107.md` and JSON for preserved r1
hashes/exit 1 and the corrected native-clock-report gate (8 Tcl regressions).
This is a tooling failure, not new RTL evidence. PM1 repair priority and
WCG1 baseline remain pending the new immutable read-only r2 STA; no synthesis
or RTL repair is performed.

The corrected immutable diagnostic r2 is now launched in
`kvzap-rd1-pm1-setup-r2:saved-sta`; use
`dc_rd1_pm1_setup_diagnosis_retry_20261107.md`/JSON for exact source, output
and log pins. It retains both original DDCs and all saved constraints; only
the ideal-clock checker changes. Eight parser regressions pass. Await user
completion notice; the PM1/WCG1 decision remains pending native results.

The saved-DDC setup diagnostic r2 is now accepted; read
`dc_rd1_pm1_setup_diagnosis_result_20261107.md`/JSON. Both native sides and
outer exit 0 close; unchanged DDC/library/script hashes recheck. Unique
negative endpoints exactly reproduce QoR counts (35,959/35,976), with summed
TNS matching rounding. PM selector worst slack degrades -0.348932 ->
-0.439257 ns; all 16 reclaim bits now fail (12 before), with low six bits
on the bank-priority/indexed-offset bottleneck. PM endpoint TNS accounts for
4.119904% of added absolute TNS; 95.880096% lands at other endpoints, an
accounting partition rather than causal proof. Common ready/request paths
outside PM worsen under complete-top remapping of unchanged RTL.
Decision: PM1 needs same-cycle selector improvement before later cumulative
integration, but does not block WCG1-only full validation. The next full
paired baseline is **RD1 + WCG1, PM1 off, RD2 excluded**; read
`dc_wcg1_full_paired_integration_baseline_20261107.md` for source/native-gate
closure and separate original-policy versus matched propagated-clock/hold
measurement tiers. RD1 is not timing-closed. No RTL repair or new tool/full-DC
job is performed by this audit. Preserve prior failed diagnostic and all
area/timing tradeoff records; do not infer whole-top WCG1 benefit or PPA.

The user authorizes RD1+WCG1 input freeze and a complete paired DC, PM1 off,
RD2 excluded, with primary and matched gated-clock/hold results separated.
Read `dc_rd1_wcg1_full_paired_launch_20261107.md` and JSON. The standalone
wrapper cannot be substituted because its header differs from the real
parent-pruned child; contextual reference/gated emission is required first.
A 3-GiB two-design JVM failed OOM and is preserved; r2 uses one 6-GiB JVM
per side in `kvzap-rd1-wcg1:export-r2`. Constructor forwarding remains
production-default-off. The new fail-closed freeze keeps 47 RD1 units and
Full-KV unchanged, replaces only the context-verified wrapper and adds the
native inline dependency (49 Route-A units). Thirty-six local regressions
pass. The guarded full pipeline must wait for export, source/state/proxy/
profile and full native-binding gates before formal compilation. Until
those markers appear this is preparation/queued execution, not input freeze
or a mapped result. Do not infer any new area/timing/cleanliness or PPA claim.

The RD1+WCG1 guarded full pipeline is now launched in
`kvzap-rd1-wcg1:paired-dc`, with its independent contextual export active in
`export-r2`. All 19 frozen script checksums pass. The last snapshot has no
export/outer completion status and no native result root: RTL freeze and
formal DC are still pending, not accepted. Export -> input/proxy/profile
checks -> full native binding -> both complete tops/three result tiers is
an automatic fail-closed chain under the user's authorization. Await user
completion notice; do not poll/restart or claim mapped results from launch.
Exact guard/bundle/log/status pins are in
`dc_rd1_wcg1_full_paired_launch_20261107.md`/JSON.
