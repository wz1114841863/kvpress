# Analysis documentation index

**先看：[项目总览与管理入口](project_overview_20261111.md)。**
该入口是面向人的精简快照；具体实验结论以对应冻结记录和结果文件为准。

算法至前 RTL 的研究过程由总览与以下六份正文完整串联，直接引用原始结果：

- [R1 算法复现、稀疏结构与路线筛选](algorithm_reports/01_reproduction_and_route_selection.md)。
- [R2 Packing、调度与摊销](algorithm_reports/02_packing_scheduling_and_amortization.md)。
- [R3 功能参考与执行观察](algorithm_reports/03_functional_reference_and_execution_observations.md)。
- [R4 跨模型与前端边界](algorithm_reports/04_cross_model_and_frontend_boundaries.md)。
- [R5 Pending与metadata资源探索](algorithm_reports/05_pending_and_metadata_resource_exploration.md)。
- [R6 前RTL成本账本与架构入口判断](algorithm_reports/06_pre_rtl_cost_ledger_and_architecture_entry.md)。

2026-11-12 已完成算法说明归并和两轮清理，研究过程只需总览与六份报告。
原始实验数据保留，资料缺口与未计成本见各报告；不再增加整编评估、来源索引
或例行哈希检查作为阅读和开发的前置条件。

## Current Route-A entry

This is the full navigation page for the active KVzap Route-A research track.
The compact classification and new-conversation read set are in
[`route_a_document_map.md`](route_a_document_map.md). It reduces routine
context without deleting, moving, or rewriting frozen evidence.

## Pending-origin and group-close contract (2026-11-09)

The [identity/lifecycle contract](route_a_pending_origin_and_window_contract_20261109.md)
and [source/reference evidence](route_a_pending_origin_and_window_contract_20261109.json)
separate true group membership from positive pending-object ownership. Group
close preserves legal nonmembers; old packed data cannot revive through an
Unseen miss or a new token. Local checks pass four positive/22 negative cases,
1,009 states/2,697 transitions and four bad-policy detections. The algorithm's
admission budget bounds service, not global pending capacity; a live catalogue
needs explicit capacity, ports and cost. These are candidate contract results,
with no production RTL/v1 change, native test, remote job or DC/STA launch.

## Registration-window contract conditional verification (2026-11-09)

The [contract verification](route_a_registration_window_contract_validation_20261109.md)
and [source/model/counterexample ledger](route_a_registration_window_contract_validation_20261109.json)
find no existing producer delivery/seal guarantee. A new freeze/disposition/
seal plus bounded owner-custody contract is consistent in a finite model
(1,693 states/4,070 transitions; seven exhaustive and three directed bad-policy
counterexamples). Issued leases can survive journal reuse, but their contexts
cannot be overwritten. Member ownership, lawful unbound sources, pending
preplan rejection and normal owner recycling remain open, so full production
rolling64 is not accepted. The Python checker changes no RTL or v1 contract;
no native test, remote job or DC/STA is started.

## Multi-group journal lifecycle and minimal plan (2026-11-09)

The [lifecycle and cost audit](route_a_multigroup_journal_lifecycle_closure_20261109.md)
and [source/width/bounds ledger](route_a_multigroup_journal_lifecycle_closure_20261109.json)
separate the existing 2,264-B working journal from cumulative exact history.
Current late lookup prevents deletion before reset. Exact migration and two
close ACKs provide a compatibility baseline; a finite registration window
requires a versioned producer-close/owner-drain contract not yet established.
Cold keep-all history can reach 9,400,320 records; the earlier 288-MiB direct
archive is a candidate, not a lower bound or an accepted physical cost.
Repeated pending-owner recycling is separately open. No RTL/test/remote/DC
work starts here, and multi-group functional acceptance remains pending.

## Persistent page read r2 bounded functional PASS (2026-11-09)

The [accepted r2 result](route_a_persistent_page_read_r2_result_20261109.md)
and [native/input/final evidence](route_a_persistent_page_read_r2_result_20261109.json)
confirm 7 suites/15 tests, matching 155 frozen sources and all five exits0.
One packing supports two real page services, error/recovery and the tested
retire cut; v1 regressions pass. Small internal-backing/gate-off/numeric0
boundaries remain, as do multi-group/journal, full scope, external service,
timing and complete-cost work. No new run or RTL change is made by acceptance.

## Persistent page read r2 launch snapshot after parent PASS (2026-11-09)

The [r2 launch](route_a_persistent_page_read_r2_launch_20261109.md) and
[frozen input/parent evidence](route_a_persistent_page_read_r2_launch_20261109.json)
record 155 checked files, compile exit0 and a qualified real R5-parent test.
Independent tmux is `kvzap-persistent-read-v2-r2:validation`; original14 tests
have started, with full15/outer acceptance pending. Parent PASS is bounded;
no full-DUT/numeric/timing or net-benefit conclusion follows yet.

## Persistent page read R5 repair candidate (2026-11-09)

The [r2 repair plan](route_a_persistent_page_read_r2_repair_20261109.md) and
[source/check ledger](route_a_persistent_page_read_r2_repair_20261109.json)
record the scanner ownership fix and real-parent mark/query/query regression.
New runner gates the original fourteen tests on the parent's native PASS,
for fifteen total; local compile/lowering and checker tests do not establish
native repair success. r1 remains preserved; no DC/STA or multi-group change.

## Persistent page read v2 r1 failure diagnosed (2026-11-09)

The [result inspection](route_a_persistent_page_read_result_20261109.md) and
[source/native/protocol evidence](route_a_persistent_page_read_result_20261109.json)
confirm a completed 11/14 run with three whole-DUT first-read failures.
R5 parent shared-lookup ownership leaves a phantom scanner outstanding bit;
no successful R5 read grant/S2 service occurs. Second-read/error/retire
capabilities remain unaccepted. Inputs and 14 native artifacts are verified,
v1 regressions pass, and this batch performs no RTL repair or new run.

## Persistent page read v2 native launch snapshot (2026-11-09)

The [launch record](route_a_persistent_page_read_launch_20261109.md) and
[frozen input/startup snapshot](route_a_persistent_page_read_launch_20261109.json)
record source `1d49fc8`, 152 hash-checked inputs and independent tmux
`kvzap-persistent-read-v2-r1:validation`. Remote compile exit0 and first
native build are observed. The 14 functional/regression tests and outer
closure remain pending; no repeated-read PASS, DC/STA or full-decode claim.

## Persistent page read implementation candidate (2026-11-09)

The [preparation record](route_a_persistent_page_read_preparation_20261109.md)
and [source/check ledger](route_a_persistent_page_read_preparation_20261109.json)
document explicit default-off v2 R5 read qualification, R6 preflight/failure,
S2 reservation and retire drain. Protected R3/Admission/M2/R2 source regions
match the baseline. Local compile/lowering and short checker gates do not
replace the planned 14-test remote native acceptance. No multi-group journal,
DC/STA, new mapped area or complete continuous-decode/numeric claim is added.

## Stage A minimal functional successor proposal (2026-11-09)

The [minimal proposal](route_a_continuation_minimal_proposal_20261109.md) and
[source/cost/model ledger](route_a_continuation_minimal_proposal_20261109.json)
assign persistent read facts to R5 and retain exact journal history before
group reuse. R6/S2 preflight, typed errors, reset/retire and physical service
cost are part of feasibility, with no unpriced external port. Nominal
read_ready is 18,360 B; a 32-B direct archive is one 288-MiB provision, not a
minimum or actual workload use. Finite protocol/format checks pass; no RTL,
contract, remote experiment, DC/STA or continuous-backend acceptance is added.

## Stage A current-RTL probe result (2026-11-09)

The [audited result](route_a_stage_a_probe_result_20261109.md) and
[native/source evidence](route_a_stage_a_probe_result_20261109.json) confirm
normal completion, four exit-0 records and 2/2 diagnostic tests. Repeated
read stops before descriptor/lease because activation facts were consumed;
the second admission stops at ingress Done. These are actual bounded
blocker reproductions after successful first service, not capability PASS.
Input/source/native artifacts are verified. No repair, rerun or DC/STA;
continuous execution, numerics, cost and timing remain open.

## Stage A current-RTL probes launched (2026-11-09)

The [remote launch](route_a_stage_a_probe_launch_20261109.md) and
[input evidence](route_a_stage_a_probe_launch_20261109.json) freeze source
`0aa5472` with unchanged production RTL. Independent tmux is
`kvzap-stage-a-probes-r1:probes`; actual input gate passes and main compilation
is the startup stage. The two diagnostic outcomes remain pending. The user
has been notified to wait; no DC/STA or automatic retry is scheduled.

## Stage A current-RTL probes prepared (2026-11-09)

The [probe preparation](route_a_stage_a_probe_preparation_20261109.md)
adds separate same-page and second-admission diagnostics around the complete
functional DUT. No production RTL changes. Static preparation checks pass;
remote compile/test and blocker evidence remain pending. A diagnostic PASS
does not close continuous execution, numeric functionality or timing.

## Stage A execution scope defined (2026-11-09)

The [lifecycle envelope](route_a_stage_a_execution_envelope_20261109.md) and
[source-pinned mapping](route_a_stage_a_execution_envelope_20261109.json)
define runtime/DUT duties, persistent-page versus transient-source lifetime,
same-page repeated-read and second-group scenario specifications. R6 terminal
and S2 release already preserve session/page lifetime; ingress/journal and
activation facts remain the concrete blockers. Numeric data correspondence
also stays open. This is scope closure only, with no new simulation, RTL,
remote experiment, timing or cost result.

## Paper scope and next closure targets (2026-11-09)

The [execution scope and closure plan](route_a_paper_execution_scope_and_closure_20261109.md)
sets a bounded, repeatable Qwen-anchor lifecycle/control prototype as the
paper implementation target. First-use functionality and WCG1 mapped-area
acceptance are preserved; sustained-use evidence, storage port/lifetime
contracts, complete incremental accounting and top-level 2ns timing remain
open. Storage-contract work and existing-DDC timing diagnosis should precede
the next implementation candidate. This document-only batch starts no job
and changes no RTL, generic compatibility, fair constraints or frozen input.

## RD1+WCG1 full paired result (2026-11-09)

The [audited result](dc_rd1_wcg1_full_paired_result_20261109.md) and
[JSON evidence](dc_rd1_wcg1_full_paired_result_20261109.json) confirm complete
native execution, all tiers and matching source/input/artifact hashes.
Primary control area decreases 11.741151% versus RD1, to 129.517x Full-KV;
setup worsens, and the equal supplemental hold pass does not close global
setup/hold on either side. Its 119.016x ratio is not a further area saving.
WCG1 is a measured area candidate, while timing, structural cleanliness,
complete incremental costs and hardware net benefit remain unresolved.
This read-only inspection starts no experiment and changes no RTL.

## RD1+WCG1 retry launch snapshot (2026-11-08)

The [r2 launch](dc_rd1_wcg1_full_paired_retry_launch_20261108.md) and
[JSON](dc_rd1_wcg1_full_paired_retry_launch_20261108.json) record the repaired
hash gate, 48 passing preparation regressions and successful real input
closure. Reuse the old contextual export; PM1 stays off and RD2 excluded.
The new independent tmux is `kvzap-rd1-wcg1-r2q1:paired-dc`. Native preflight
is active after resource admission; a clean preflight automatically starts
the complete pair with all three original/propagated/hold tiers preserved.
No area/timing result is inferred. Wait for the user's completion notice.

## Latest RD1+WCG1 result inspection (2026-11-07)

The [full-paired inspection](dc_rd1_wcg1_full_paired_inspection_20261107.md)
and [evidence JSON](dc_rd1_wcg1_full_paired_inspection_20261107.json) confirm
contextual export r2 completed, but the pipeline failed at input freeze
before native binding or either DC side. The script compared canonical helper
bytes with the raw emitted-file hash; both actual representations and the
helper body match accepted WCG1 inputs. No new full-top area/timing result
exists. The read-only inspection preserves all failed artifacts and starts no
repair/retry. The earlier launch and deep-review snapshots remain historical.

## Current research review (2026-11-07)

The [`deep review`](route_a_deep_review_20261107.md) reconnects original
KVzap evidence, Route-A model/architecture choices, actual RTL execution
scope, complete incremental costs and all major control-refinement results.
Its [`evidence ledger`](route_a_deep_review_evidence_20261107.json) records
source pins, current local hash/arithmetic checks, missing provenance and
finite closure conditions. Read it for a research retrospective or a decision
about the next implementation stage; use the living
[`handoff`](route_a_current_handoff.md) for individual experiments.

Conditional algorithm/model opportunities, bounded functional closure and
mapped control-area improvements remain valid within their stated scope.
Sustained service, complete incremental affordability and full-top 2-ns setup
closure remain unresolved. RD1+WCG1 has a separately authorized guarded
pipeline; its last local launch snapshot is not a completed result, and this
review does not poll or affect it. No RTL or new experiment is performed.
The dated detailed status below is preserved as historical context.

## Historical disposition (2026-10-17)

A4.11--A4.14.1 research DSE, architecture Reviewer-02, Gate-RTL0, RTL1,
RTL2, and RTL3 functional-subsystem closure have each completed at their
declared evidence levels. RTL3.9-C0--C4-D now close the published packed
first-use path through S2, source service, one terminal, retirement/reclaim,
accepted-event replay, and bounded stale/mismatch/fault/reset coverage.

The current conclusion is **functional-subsystem closure only**. It does not
establish a synthesizable partition, controller/macro, HBM/SRAM behavior,
numeric datapath, timing, throughput, PPA, model/GPU result, or complete
inference.  SRP (Synthesis-Realization Partition & Eligibility Review) has
completed its SRP.0--SRP.1-R provenance/source inventory and
revised partition proposal passed human review; SRP.2 source/toolchain
eligibility, SRP.3 realization-requirements planning, SRP.4 differential-cost
evidence planning, and SRP.5 completion review are complete at their declared
planning scopes.  MBR.0 (Measurement Boundary Review) has passed human review
for its candidate control/protocol measurement cut and complete
source/partition BOM.  MBR.1 fairness planning and MBR.1-A
implementation-preparation have passed external technical review and received
explicit user approval. The targeted Full-KV source audit initially found the
three legal baseline paths absent. W0 has now completed its bounded dual-DUT
functional contour, and MR-1A has completed the approved Route-A-hot plus
Full-KV common lifecycle/status integration. MR-1B direct-pending source-plan
association now has a narrow
[`mr1b_direct_pending_cross_owner_contract_proposal.md`](mr1b_direct_pending_cross_owner_contract_proposal.md)
awaiting user approval; independent MR-2 array-only storage-boundary work may
proceed. The P3-only first batch is recorded in
[`mr2_p3_array_boundary_contract.md`](mr2_p3_array_boundary_contract.md) and
the S2 payload/sidecar batch has isolated and directed-tested its logical
array interior, recorded in
[`mr2_s2_array_boundary_contract.md`](mr2_s2_array_boundary_contract.md).
Both remain short of any wrapper selection. None
of this is a selected future synthesis top or physical implementation. The separate
[R6 前RTL成本账本](algorithm_reports/06_pre_rtl_cost_ledger_and_architecture_entry.md)
has restored the ignored A4.14.1 report/input closure locally and passed its
original preflight; this permits only read-only revalidation of the accepted
proxy-ledger constraints, not a physical or net-benefit conclusion.
See
[`synthesis_realization_partition.md`](synthesis_realization_partition.md),
[`srp3_realization_requirements_decision_plan.md`](srp3_realization_requirements_decision_plan.md),
[`srp4_differential_cost_evidence_plan.md`](srp4_differential_cost_evidence_plan.md),
[`srp5_completion_review.md`](srp5_completion_review.md),
[`measurement_boundary_selection.md`](measurement_boundary_selection.md),
[`measurement_boundary_bom.json`](measurement_boundary_bom.json),
[`measurement_baseline_fairness_plan.md`](measurement_baseline_fairness_plan.md),
[`measurement_baseline_matrix.json`](measurement_baseline_matrix.json),
[`measurement_realization_candidate_proposal.md`](measurement_realization_candidate_proposal.md),
[`measurement_realization_candidate_manifest.json`](measurement_realization_candidate_manifest.json),
[`full_kv_baseline_path_audit_20261016.md`](full_kv_baseline_path_audit_20261016.md),
[`full_kv_baseline_path_audit_20261016.json`](full_kv_baseline_path_audit_20261016.json),
[`route_a_current_handoff.md`](route_a_current_handoff.md), and
[`rtl3_9_c4_d_functional_completion_review.md`](rtl3_9_c4_d_functional_completion_review.md).

### Historical detailed status (through RTL3.7)

A4.11--A4.14 research DSE is closed; Reviewer-02
passed the R1--R6 architecture cross-closure; Gate-RTL0 passed and RTL1
owner-local control is complete. RTL1-I1--I4 have subsequently closed safe
start/empty retirement, retained-record publication association,
source-instance/R6 completion, and R5 reclaim through the unique R2/R1 path;
RTL1-V subsequently closed the remaining bounded verification/scoreboard
bindings. RTL2.0 has now closed its seven pre-behavior producer/interface
amendments, passed cross-owner completion review, and frozen a versioned
scoreboard-event schema. RTL2.1a--RTL2.1c atomic-publication behavior and
RTL2.2 read/write delivery prerequisites are implemented and directed tested.
RTL2.3.0--.3 plus C1--C5 close read-endpoint preparation and structural R4
packet ingress. RTL2.3-C6 binds the non-top source-plan producer and RTL2.3-C7
connects its R6 plan copy plus exact source-owner observations to the packet
adapter. RTL2.3-C8 closes four-consumer release and R6 merge-request
association in a verification-packet integration harness. RTL2.3-C9 now binds
the C2/C3/C4 endpoints through one descriptor-selected top composition path
with explicitly non-production verification ingress. RTL2.3 therefore passes
`control_protocol_complete`; it remains neither numeric attention
nor production end-to-end dataflow. RTL2.3-R records the active event-phase
map. RTL2.4.0 has frozen the verification-only result/fault-stub terminal
contract, and RTL2.4.1 has closed its isolated test-scope provider behavior.
RTL2.4.2 has now bound it through the real R4/R6 terminal chain in a test-only
harness, and RTL2.4.3 binds its named terminal event to the testbench adapter
and Python lifecycle reference. The RTL2.4 completion review has passed
without reopening numeric realization, controller, native-HBM, or performance
scope. RTL2.5.0 now freezes the reset/fault/retirement/reclaim owner and event
contract. RTL2.5.1 has directed reset-epoch evidence for active R1/R5/source
state and top-level re-init. RTL2.5.2 closes the narrow directed R4--R6
numeric-fault terminal boundary: one stable terminal/event, stale/malformed
and replay rejection, and no retry or Full-KV-fallback interface. Retirement
drain now has fixed-membership and bounded-fairness witnesses in RTL2.5.3;
RTL2.5.4 closes R5's matching durable invalidation-before-generation/free
boundary. RTL2.5.5-I additionally connects real R5/R6 named carriers through
the testbench adapter before replaying their fixed field trace through Python;
it is not a production-top scoreboard or a physical-memory claim.
RTL2.6.0 has completed the machine-readable entry audit: only four of the
fourteen declared events are testbench-bound, so its disposition remains
explicitly incomplete pending a single real-owner retained-transaction witness
and the remaining ten event bindings.
RTL2.6.1 now freezes exact no-default field provenance for those ten records;
it intentionally does not yet claim that a composed Chisel harness captures
or emits them. RTL2.6.2a now composes the real packed S2 source-release and
R4/R6 terminal segment in one test-only instance, while preserving the
remaining R3/R5-to-S2 association and full retained-transaction witness as
open work. RTL2.6.3 has now frozen that association as an explicit,
fail-closed verification adapter; it is still not a production bridge.
RTL2.6.4 uses it in one same-instance publication-to-fault-terminal witness,
but still leaves full completion/reclaim and scoreboard replay open. RTL2.6.5
is now the explicit final full-witness gate; its ordered read, reclaim, event,
and review sub-slices are recorded in the RTL2.6 completion review. RTL2.6.5a.1
has replaced direct S2 payload injection with the typed packed-S2 R2/R1 path;
RTL2.6.5a.2 now likewise replaces direct P3 payload injection with the
existing R3 pack-read through typed R2/R1 delivery, then its existing
packed-write/descriptor/publication sequence. RTL2.6.5b then composes the
existing R6 terminal, explicit matching environment retirement, R5 durable
reclaim, and global `retire_ack`. RTL2.6.5c closes the accepted-carrier
event-capture/Python-oracle replay boundary. RTL2.6.5d then recorded the
historical no-PASS because the passing pieces were not yet one same-instance
real-owner retained transaction. RTL2.6.5e now closes that narrow testbench
witness: it composes R3 publication, real S2 service/terminal, and the same
R5 durable reclaim to `retire_ack` in one Chisel instance. Its completion is
strictly testbench-only functional transaction/dataflow evidence, not a
production top, numeric/memory realization, or performance claim. The planned
RTL3 successor begins with a replacement-owner manifest, then separately
closes functional memory, S2 read, R4 functional merge, and the independent
partial-producer boundary; it must not assign attention computation to a K/V
storage owner. RTL3.0 completed that planning manifest with explicit
packed-read-association and query/position partial-provider stop-for-review
items. RTL3.1 subsequently completed only a testbench-side functional R1
memory environment. RTL3.2-A now resolves the packed-read association-owner
contract, while the partial-provider query/position stop remains; no production
RTL3 closure is authorized.

RTL3.6-A repaired active accepted-carrier replay provenance only. RTL3.6-B
then closed the narrow same-instance static functional-provider/R4-terminal
witness: four Python-generated packed packet fixtures traverse the Chisel
source/R4 boundary before matching static functional-oracle terminals reach R6
and same-R5 reclaim. S2 fill/sidecar ingress and full reset-epoch composition
remain open, so RTL3 functional realization is not complete.

RTL3.6-C1 now replaces the RTL3.2 harness's direct sidecar ingress with a
named handle-keyed fixture transport and exact S2 fill observation. This is
still testbench-only. RTL3.6-C2 now composes that source path with real R3
publication, static functional terminal, R6 retirement, and same-R5 reclaim,
and adds dual-R1 reset stale-response suppression/re-init evidence. The C2
source read remains a separately-bound test-harness R1 path and its
publication/descriptor/lease inputs remain verification facts, so this is not
a production common-memory realization. RTL3 completion still requires a
cross-owner review. RTL3.7-A further closes only shared functional object
continuity: C2 consumes the exact eight-fragment object written durably by R3
through a host-side store shared by the two test harness endpoints. Its
fragment-count key is not a deployed address format; C2 grants and sidecar/R4
fixtures remain open. RTL3.7-B additionally closes the testbench-only C2
terminal/release/retire order: every endpoint terminal reaches S2, only the
final one releases the frozen association, and that release is observed before
the matching retire enters existing R6/R5 drain/reclaim. It does not alter the
production top or R6 global-membership collection. RTL3.7-C then closes the
bounded C2 membership gap in the test harness: matching existing C2 and
publication R1/R2 status facts join before the unchanged collector, including
R1 init/drain and both R2 drain kinds. Its host-side event oracle covers a
legal response stall; directed inherited checks cover stale-after-reset and
fail-closed endpoint-fault behavior. It does not make C2 grants, C1 sidecar
transport, or static partial/R4 fixtures functional producers.

## Current architecture and verification records

Read these only when the corresponding level of detail is required:

| Need | Primary record |
|---|---|
| Current interface, frozen/parameterized/unestimated fields, omitted-cost constraints | [`architecture_spec.md`](architecture_spec.md) |
| Gate-A final cross-closure decision | [`architecture_gate_a_reviewer_02.md`](architecture_gate_a_reviewer_02.md) |
| Cross-closure matrix and integration amendments | [`architecture_gate_a_pre_reviewer_02_integration_audit.md`](architecture_gate_a_pre_reviewer_02_integration_audit.md) |
| Exact byte bindings for the final review | [`architecture_gate_a_reviewer_02_provenance_freeze.md`](architecture_gate_a_reviewer_02_provenance_freeze.md) |
| Route-A RTL/profile anchor | [`architecture_gate_a3_plan.md`](architecture_gate_a3_plan.md) and `architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` |
| Gate-RTL0 hierarchy and sole-owner split | [`rtl_entry_hierarchy_owner_contract.md`](rtl_entry_hierarchy_owner_contract.md), [`rtl_entry_interface_manifest.json`](rtl_entry_interface_manifest.json), and [`rtl_entry_hierarchy_owner_provenance_freeze.md`](rtl_entry_hierarchy_owner_provenance_freeze.md) |
| Gate-RTL0 logical port/parameter matrix | [`rtl_entry_port_parameter_contract.md`](rtl_entry_port_parameter_contract.md), [`rtl_entry_port_parameter_provenance_freeze.md`](rtl_entry_port_parameter_provenance_freeze.md), and `tools/validate_rtl_entry_interface_manifest.py` |
| Gate-RTL0 assertion/scoreboard/coverage plan | [`rtl_entry_assertion_verification_contract.md`](rtl_entry_assertion_verification_contract.md) and [`rtl_entry_assertion_matrix.json`](rtl_entry_assertion_matrix.json) |
| RTL1-V executable verification closure | [`rtl1_v_verification_completion_contract.md`](rtl1_v_verification_completion_contract.md), [`rtl1_v_scoreboard_event_schema.json`](rtl1_v_scoreboard_event_schema.json), and [`rtl1_v_provenance_freeze.md`](rtl1_v_provenance_freeze.md) |
| RTL2 completion disposition and planned RTL3 functional-realization closure | [`rtl2_phase_contract.md`](rtl2_phase_contract.md) |
| RTL3.0 replacement-owner / stop-for-review map | [`rtl3_0_replacement_owner_contract.md`](rtl3_0_replacement_owner_contract.md) and [`rtl3_0_replacement_owner_manifest.json`](rtl3_0_replacement_owner_manifest.json) |
| RTL3.1 testbench-only functional memory environment | [`rtl3_1_functional_memory_environment_contract.md`](rtl3_1_functional_memory_environment_contract.md) and [`rtl3_1_functional_memory_environment_manifest.json`](rtl3_1_functional_memory_environment_manifest.json) |
| RTL3.2-A packed-read association owner | [`rtl3_2a_packed_read_association_contract.md`](rtl3_2a_packed_read_association_contract.md) and [`rtl3_2a_packed_read_association_manifest.json`](rtl3_2a_packed_read_association_manifest.json) |
| RTL3.2 composed functional packed payload to S2 | [`rtl3_2_packed_read_functional_integration_contract.md`](rtl3_2_packed_read_functional_integration_contract.md) and [`rtl3_2_packed_read_functional_integration_manifest.json`](rtl3_2_packed_read_functional_integration_manifest.json) |
| RTL3.3 R4 functional profile / oracle binding | [`rtl3_3_r4_functional_profile_contract.md`](rtl3_3_r4_functional_profile_contract.md) and [`rtl3_3_r4_functional_profile_manifest.json`](rtl3_3_r4_functional_profile_manifest.json) |
| RTL3.4-A R4 per-consumer result association | [`rtl3_4a_r4_consumer_result_association_contract.md`](rtl3_4a_r4_consumer_result_association_contract.md) and [`rtl3_4a_r4_consumer_result_association_manifest.json`](rtl3_4a_r4_consumer_result_association_manifest.json) |
| RTL3.4-B functional R4 oracle provider | [`rtl3_4b_functional_r4_provider_contract.md`](rtl3_4b_functional_r4_provider_contract.md) and [`rtl3_4b_functional_r4_provider_manifest.json`](rtl3_4b_functional_r4_provider_manifest.json) |
| RTL3.5-A query/position/RoPE and partial-producer boundary | [`rtl3_5a_attention_partial_producer_boundary_contract.md`](rtl3_5a_attention_partial_producer_boundary_contract.md) and [`rtl3_5a_attention_partial_producer_boundary_manifest.json`](rtl3_5a_attention_partial_producer_boundary_manifest.json) |
| RTL3.5-B functional partial-provider reference model | [`rtl3_5b_functional_attention_partial_provider_contract.md`](rtl3_5b_functional_attention_partial_provider_contract.md) and [`rtl3_5b_functional_attention_partial_provider_manifest.json`](rtl3_5b_functional_attention_partial_provider_manifest.json) |
| RTL3.5-C static cross-language partial-packet binding | [`rtl3_5c_cross_language_packet_binding_contract.md`](rtl3_5c_cross_language_packet_binding_contract.md) and [`rtl3_5c_cross_language_packet_binding_manifest.json`](rtl3_5c_cross_language_packet_binding_manifest.json) |
| RTL3.6 functional-realization completion review | [`rtl3_6_functional_realization_completion_review.md`](rtl3_6_functional_realization_completion_review.md) and [`rtl3_6_functional_realization_completion_review_manifest.json`](rtl3_6_functional_realization_completion_review_manifest.json) |
| RTL3.6-A active replay provenance repair | [`rtl3_6a_active_replay_provenance_repair_contract.md`](rtl3_6a_active_replay_provenance_repair_contract.md) and [`rtl3_6a_active_replay_provenance_repair_manifest.json`](rtl3_6a_active_replay_provenance_repair_manifest.json) |
| RTL3.6-B static same-instance provider/terminal witness | [`rtl3_6b_same_instance_functional_provider_terminal_contract.md`](rtl3_6b_same_instance_functional_provider_terminal_contract.md) and [`rtl3_6b_same_instance_functional_provider_terminal_manifest.json`](rtl3_6b_same_instance_functional_provider_terminal_manifest.json) |
| RTL3.6-C1 named sidecar fixture transport | [`rtl3_6c1_sidecar_fixture_transport_contract.md`](rtl3_6c1_sidecar_fixture_transport_contract.md) and [`rtl3_6c1_sidecar_fixture_transport_manifest.json`](rtl3_6c1_sidecar_fixture_transport_manifest.json) |
| RTL3.6-C2 same-instance dataflow/reset-epoch witness | [`rtl3_6c2_same_instance_dataflow_reset_contract.md`](rtl3_6c2_same_instance_dataflow_reset_contract.md) and [`rtl3_6c2_same_instance_dataflow_reset_manifest.json`](rtl3_6c2_same_instance_dataflow_reset_manifest.json) |
| RTL3.7-A shared functional-memory object continuity | [`rtl3_7a_shared_functional_memory_continuity_contract.md`](rtl3_7a_shared_functional_memory_continuity_contract.md) and [`rtl3_7a_shared_functional_memory_continuity_manifest.json`](rtl3_7a_shared_functional_memory_continuity_manifest.json) |
| RTL3.7-B C2 terminal/release/retire ordering | [`rtl3_7b_terminal_release_global_drain_contract.md`](rtl3_7b_terminal_release_global_drain_contract.md) and [`rtl3_7b_terminal_release_global_drain_manifest.json`](rtl3_7b_terminal_release_global_drain_manifest.json) |
| RTL3.7-C C2 drain membership / fault-stall-reset event-scoreboard closure | [`rtl3_7c_drain_fault_stall_reset_scoreboard_contract.md`](rtl3_7c_drain_fault_stall_reset_scoreboard_contract.md) and [`rtl3_7c_drain_fault_stall_reset_scoreboard_manifest.json`](rtl3_7c_drain_fault_stall_reset_scoreboard_manifest.json) |
| RTL3 completion cross-owner review 03 | [`rtl3_completion_cross_owner_review_03.md`](rtl3_completion_cross_owner_review_03.md) and [`rtl3_completion_cross_owner_review_03_manifest.json`](rtl3_completion_cross_owner_review_03_manifest.json) |
| RTL3.8.0 functional-closure ingress retirement freeze | [`rtl3_8_0_functional_closure_ingress_retirement_contract.md`](rtl3_8_0_functional_closure_ingress_retirement_contract.md) and [`rtl3_8_0_functional_closure_ingress_retirement_manifest.json`](rtl3_8_0_functional_closure_ingress_retirement_manifest.json) |
| RTL3.8.1--RTL3.8.5 functional-top activation and all-source directed coverage | [`rtl3_8_5_full_path_closure_coverage_contract.md`](rtl3_8_5_full_path_closure_coverage_contract.md) and [`rtl3_8_5_full_path_closure_coverage_manifest.json`](rtl3_8_5_full_path_closure_coverage_manifest.json) |
| RTL3.9-A pending payload materialization/read activation | [`rtl3_9_a_r3_pending_pack_read_activation_contract.md`](rtl3_9_a_r3_pending_pack_read_activation_contract.md) and [`rtl3_9_a_r3_pending_pack_read_activation_manifest.json`](rtl3_9_a_r3_pending_pack_read_activation_manifest.json) |
| RTL3.9-B1/B2 durable packed payload and descriptor activation | [`rtl3_9_b1_r3_packed_write_activation_contract.md`](rtl3_9_b1_r3_packed_write_activation_contract.md) and [`rtl3_9_b2_descriptor_durability_activation_contract.md`](rtl3_9_b2_descriptor_durability_activation_contract.md) |
| RTL3.9-B3 atomic publication, R5 visibility, and R6 authority acceptance | [`rtl3_9_b3_atomic_publication_authority_activation_contract.md`](rtl3_9_b3_atomic_publication_authority_activation_contract.md) and [`rtl3_9_b3_atomic_publication_authority_activation_manifest.json`](rtl3_9_b3_atomic_publication_authority_activation_manifest.json) |
| RTL2.3 active phase/event reconciliation | [`rtl2_3_reconciliation_01.md`](rtl2_3_reconciliation_01.md) and [`rtl2_scoreboard_event_phase_reconciliation_01.json`](rtl2_scoreboard_event_phase_reconciliation_01.json) |
| RTL2.3-C6 R6 source-plan producer | [`rtl2_3_c6_source_plan_binder_contract.md`](rtl2_3_c6_source_plan_binder_contract.md) and [`rtl2_3_c6_source_plan_binder_manifest.json`](rtl2_3_c6_source_plan_binder_manifest.json) |
| RTL2.3-C7 source-service top integration | [`rtl2_3_c7_source_service_top_integration_contract.md`](rtl2_3_c7_source_service_top_integration_contract.md) and [`rtl2_3_c7_source_service_top_integration_manifest.json`](rtl2_3_c7_source_service_top_integration_manifest.json) |
| RTL2.3-C8 four-consumer completion / R6 merge request | [`rtl2_3_c8_four_consumer_completion_contract.md`](rtl2_3_c8_four_consumer_completion_contract.md) and [`rtl2_3_c8_four_consumer_completion_manifest.json`](rtl2_3_c8_four_consumer_completion_manifest.json) |
| RTL2.3-C9 authorized top endpoint composition | [`rtl2_3_c9_top_endpoint_composition_contract.md`](rtl2_3_c9_top_endpoint_composition_contract.md) and [`rtl2_3_c9_top_endpoint_composition_manifest.json`](rtl2_3_c9_top_endpoint_composition_manifest.json) |
| RTL2.4.0 R4 verification-stub terminal contract | [`rtl2_4_0_r4_stub_terminal_contract.md`](rtl2_4_0_r4_stub_terminal_contract.md) and [`rtl2_4_0_r4_stub_terminal_manifest.json`](rtl2_4_0_r4_stub_terminal_manifest.json) |
| RTL2.4.1 isolated R4 verification-stub provider | [`rtl2_4_1_r4_stub_provider_contract.md`](rtl2_4_1_r4_stub_provider_contract.md) and [`rtl2_4_1_r4_stub_provider_manifest.json`](rtl2_4_1_r4_stub_provider_manifest.json) |
| RTL2.4.2 R4--R6 verification terminal chain | [`rtl2_4_2_r4_r6_terminal_integration_contract.md`](rtl2_4_2_r4_r6_terminal_integration_contract.md) and [`rtl2_4_2_r4_r6_terminal_integration_manifest.json`](rtl2_4_2_r4_r6_terminal_integration_manifest.json) |
| RTL2.4.3 attention-terminal scoreboard/oracle binding | [`rtl2_4_3_attention_terminal_scoreboard_contract.md`](rtl2_4_3_attention_terminal_scoreboard_contract.md) and [`rtl2_4_3_attention_terminal_scoreboard_binding.json`](rtl2_4_3_attention_terminal_scoreboard_binding.json) |
| RTL2.5.0 lifecycle/reset/reclaim closure contract | [`rtl2_5_0_lifecycle_reclaim_contract.md`](rtl2_5_0_lifecycle_reclaim_contract.md) and [`rtl2_5_0_lifecycle_reclaim_manifest.json`](rtl2_5_0_lifecycle_reclaim_manifest.json) |
| RTL2.5.1 destructive-reset active-state closure | [`rtl2_5_1_destructive_reset_contract.md`](rtl2_5_1_destructive_reset_contract.md) and [`rtl2_5_1_destructive_reset_manifest.json`](rtl2_5_1_destructive_reset_manifest.json) |
| RTL2.5.2 fault / terminal cross-owner closure | [`rtl2_5_2_fault_terminal_contract.md`](rtl2_5_2_fault_terminal_contract.md) and [`rtl2_5_2_fault_terminal_manifest.json`](rtl2_5_2_fault_terminal_manifest.json) |
| RTL2.5.3 R6 retirement / drain fixed-membership closure | [`rtl2_5_3_retirement_drain_contract.md`](rtl2_5_3_retirement_drain_contract.md) and [`rtl2_5_3_retirement_drain_manifest.json`](rtl2_5_3_retirement_drain_manifest.json) |
| RTL2.5.4 R5 durable invalidation-before-free closure | [`rtl2_5_4_r5_durable_invalidation_contract.md`](rtl2_5_4_r5_durable_invalidation_contract.md) and [`rtl2_5_4_r5_durable_invalidation_manifest.json`](rtl2_5_4_r5_durable_invalidation_manifest.json) |
| RTL2.5.5 R5/R6 active-state scoreboard/oracle binding | [`rtl2_5_5_active_state_scoreboard_contract.md`](rtl2_5_5_active_state_scoreboard_contract.md), [`rtl2_5_5_active_state_scoreboard_binding.json`](rtl2_5_5_active_state_scoreboard_binding.json), and [`rtl2_5_5_active_state_scoreboard_manifest.json`](rtl2_5_5_active_state_scoreboard_manifest.json) |
| RTL2.6 completion review: historical entry audit plus constrained functional disposition | [`rtl2_6_completion_review.md`](rtl2_6_completion_review.md), [`rtl2_6_completion_review_manifest.json`](rtl2_6_completion_review_manifest.json), and [`rtl2_6_5e_same_instance_witness_manifest.json`](rtl2_6_5e_same_instance_witness_manifest.json) |
| RTL2.6.1 event field-provenance binding | [`rtl2_6_1_event_binding_contract.md`](rtl2_6_1_event_binding_contract.md) and [`rtl2_6_1_event_binding_manifest.json`](rtl2_6_1_event_binding_manifest.json) |
| RTL2.6.2a narrow composed packed-source terminal harness | [`rtl2_6_2_composed_packed_source_harness_contract.md`](rtl2_6_2_composed_packed_source_harness_contract.md) |
| RTL2.6.3 publication-to-S2 verification association | [`rtl2_6_3_publication_s2_association_contract.md`](rtl2_6_3_publication_s2_association_contract.md) |
| RTL2.6.4 single-instance publication-to-terminal witness | [`rtl2_6_4_publication_to_terminal_composition_contract.md`](rtl2_6_4_publication_to_terminal_composition_contract.md) |
| RTL2.6.5a.1 actual packed-S2 read composition | [`rtl2_6_5a_packed_s2_read_composition_contract.md`](rtl2_6_5a_packed_s2_read_composition_contract.md) |
| RTL2.6.5a.2 R3 pack-read/P3/publication composition | [`rtl2_6_5a2_r3_pack_read_p3_composition_contract.md`](rtl2_6_5a2_r3_pack_read_p3_composition_contract.md) |
| RTL2.6.5b terminal-to-reclaim composition | [`rtl2_6_5b_terminal_reclaim_composition_contract.md`](rtl2_6_5b_terminal_reclaim_composition_contract.md) |
| RTL2.6.5c accepted-carrier event capture / oracle replay | [`rtl2_6_5c_event_capture_replay_contract.md`](rtl2_6_5c_event_capture_replay_contract.md) and [`rtl2_6_5c_event_capture_replay_manifest.json`](rtl2_6_5c_event_capture_replay_manifest.json) |
| RTL2.6.5d cross-owner completion review (no PASS) | [`rtl2_6_5d_completion_review.md`](rtl2_6_5d_completion_review.md) and [`rtl2_6_5d_completion_review.json`](rtl2_6_5d_completion_review.json) |
| RTL2.6.5e same-instance real-owner witness / constrained re-review | [`rtl2_6_5e_same_instance_witness_contract.md`](rtl2_6_5e_same_instance_witness_contract.md) and [`rtl2_6_5e_same_instance_witness_manifest.json`](rtl2_6_5e_same_instance_witness_manifest.json) |
| RTL2.0 producer/event activation inventory | [`rtl2_0_activation_contract.md`](rtl2_0_activation_contract.md) and [`rtl2_0_activation_manifest.json`](rtl2_0_activation_manifest.json) |
| RTL2.0a logical payload materialization / hot maturity egress | [`rtl2_0a_payload_materialization_contract.md`](rtl2_0a_payload_materialization_contract.md) and [`rtl2_0a_payload_materialization_manifest.json`](rtl2_0a_payload_materialization_manifest.json) |
| RTL2.0b retained admission-group builder | [`rtl2_0b_admission_group_builder_contract.md`](rtl2_0b_admission_group_builder_contract.md) and [`rtl2_0b_admission_group_builder_manifest.json`](rtl2_0b_admission_group_builder_manifest.json) |
| RTL2.0c R2 logical ingress / delivery-context ownership | [`rtl2_0c_r2_ingress_delivery_context_contract.md`](rtl2_0c_r2_ingress_delivery_context_contract.md) and [`rtl2_0c_r2_ingress_delivery_context_manifest.json`](rtl2_0c_r2_ingress_delivery_context_manifest.json) |
| RTL2.0d typed read-fragment / write-terminal router endpoints | [`rtl2_0d_typed_delivery_router_contract.md`](rtl2_0d_typed_delivery_router_contract.md) and [`rtl2_0d_typed_delivery_router_manifest.json`](rtl2_0d_typed_delivery_router_manifest.json) |
| RTL2.0e R3/R5 descriptor-durability prerequisite | [`rtl2_0e_r3_r5_durability_prerequisite_contract.md`](rtl2_0e_r3_r5_durability_prerequisite_contract.md) and [`rtl2_0e_r3_r5_durability_prerequisite_manifest.json`](rtl2_0e_r3_r5_durability_prerequisite_manifest.json) |
| RTL2.0f source-service packet adapter | [`rtl2_0f_source_service_packet_adapter_contract.md`](rtl2_0f_source_service_packet_adapter_contract.md) and [`rtl2_0f_source_service_packet_adapter_manifest.json`](rtl2_0f_source_service_packet_adapter_manifest.json) |
| RTL2.0g R4 verification-only result-stub provider | [`rtl2_0g_r4_result_stub_provider_contract.md`](rtl2_0g_r4_result_stub_provider_contract.md) and [`rtl2_0g_r4_result_stub_provider_manifest.json`](rtl2_0g_r4_result_stub_provider_manifest.json) |
| RTL2.0 completion review and versioned pre-behavior scoreboard schema | [`rtl2_0_completion_review.md`](rtl2_0_completion_review.md), [`rtl2_0_completion_review_manifest.json`](rtl2_0_completion_review_manifest.json), and [`rtl2_scoreboard_event_schema.json`](rtl2_scoreboard_event_schema.json) |
| RTL2.1a immutable retained-group/admission activation | [`rtl2_1a_retained_group_admission_contract.md`](rtl2_1a_retained_group_admission_contract.md) and [`rtl2_1a_retained_group_admission_manifest.json`](rtl2_1a_retained_group_admission_manifest.json) |
| RTL1-I3 source/R4/R6 control composition | [`rtl1_i3_delivery_source_contract.md`](rtl1_i3_delivery_source_contract.md) and [`rtl1_i3_interface_manifest.json`](rtl1_i3_interface_manifest.json) |
| RTL1-I4 reclaim transport contract | [`rtl1_i4_reclaim_contract.md`](rtl1_i4_reclaim_contract.md) and [`rtl1_i4_interface_manifest.json`](rtl1_i4_interface_manifest.json) |

The hardware R1--R6 closure contracts (distinct from the six algorithm reports
above) and their Python references remain the precise executable attachments
to the specification. They are not parallel living architecture
specifications: use them for module-level interface/assertion work or exact
historical provenance.

## A4 research and saved results

Read [R5](algorithm_reports/05_pending_and_metadata_resource_exploration.md)
for pending/metadata execution and queues, and
[R6](algorithm_reports/06_pre_rtl_cost_ledger_and_architecture_entry.md)
for external-storage semantics, payload, cost and the architecture-entry decision.
The [saved A4.14.1 result](experiments/route_a4141_accounted_net_benefit_ledger_01/a4141_accounted_net_benefit_ledger_report.json)
and its `input_artifacts/` contain the underlying results. These remain
conditional model/proxy evidence rather than physical HBM, PPA or speedup.

## Historical material

Research explanations now live in the project overview and R1—R6. Covered
old plans, handoffs, cost-contract descriptions and recovery prose have been
removed. Original data and historical freeze records have not been rewritten.
If an old record names a removed document, read that document at the record's
Git revision; the pre-cleanup snapshot `42048b2` also contains the retired
algorithm documents and old AGENTS. No separate archive folder is needed.

The retained cross-frontend Markdown archive is an input to the historical C0
collector. It is not required reading: C1 onward uses the saved JSON reports.
Current AGENTS contains development constraints; historical hashes do not
prevent editing current documentation or implementing work authorized by the user.

## Maintenance rule

Update the appropriate living document when a gate or experiment changes
current status: refresh `route_a_current_handoff.md` for the compact current
disposition, refresh `route_a_document_map.md` when the core/stage retrieval
classification changes, append detailed RTL phase progress to
`rtl2_phase_contract.md`, append compatible trace schema records to
`TRACE_SCHEMA.md`, and update the relevant report in `algorithm_reports/`
and `project_overview_20261111.md` for research interpretation and current
status. Update `architecture_spec.md` for accepted
interface-contract changes or a clearly labelled status alignment. Create a
new numbered volume only when a continuous living record becomes impractical
to navigate. The specifically named current handoff is a living document;
dated/archived handoffs, freezes, provenance, and experiment records remain
append-free historical evidence unless a separately authorized correction is
required.

## Documentation-consolidation revision (2026-09-29)

This navigation revision consolidates current status into the living documents
above. It changes no frozen experiment, provenance, handoff, historical schema
section, Route-A semantic contract, or reported result. Earlier provenance
freezes remain byte snapshots of their own reviewed revisions; they are not
expected to hash-match a later living-document revision. Git history and the
current review/provenance links provide the continuity between such revisions.
