# RTL1 — Interface / Control Skeleton Bring-up

**Status:** `rtl1_2_r2_arbiter_complete_at_module_scope; rtl1_3_0_r3_r5_carriers_complete; top_integration_and_remaining_owner_phases_pending`.

RTL1 may not change frozen owners, ports, assertions, oracles, pruning,
admission, scheduler semantics, page size, S2 count, outstanding bounds, merge
format, or physical realization parameters.

| Phase | Scope | Evidence before advance |
|---|---|---|
| RTL1.0 | Top/all skeletons, ports, reset, ready/valid, SVA/TB/scoreboard attachment | compile/elaboration clean; no behavior claim |
| RTL1.1 | R1 identity/fragment/terminal/reset-init/stale suppression | R1 assertions/oracle tests |
| RTL1.2 | R2 eligibility/FIFO/credit/grant-on-accept | R2 assertions/interleavings |
| RTL1.3 | coupled R3/R5 P3/descriptor/atomic publication | durable-only/one-commit assertions |
| RTL1.4 | S2/direct-pending/four-consumer release | generation/stale/GQA assertions |
| RTL1.5 | R6 lifecycle/terminal/retirement/global drain | authority/terminal/retire assertions |
| RTL1.6 | R4 boundary only | packet/fault binding; no exp/FP RTL claim |

CDC/HBM adapter, macro/port count, physical queues, frequency, timing, PPA,
and speedup remain outside RTL1 and require later implementation/Gate-B evidence.

## RTL1.3.0 progress

**RTL1.3.0 R3/R5 semantic-carrier closure: complete.**
`analysis/rtl1_3_r3_r5_semantic_carrier_contract.md` freezes the local
control-only P3 claim/fragment/sidecar/write-terminal, two-member M2 result,
R5 allocation, and descriptor-terminal carriers. The frozen external
publication triplet and the sole R1 external-memory carrier are unchanged.
The top keeps these local carriers inactive until their producer-owner phases
exist, so this step contains no P3/M2/R5 behavior or authority change. The
structural Chisel elaboration test passed after the carrier addition.

## RTL1.0 progress

**RTL1.0.a structural skeleton: complete.** The Chisel implementation at
`hardware/route_a/chisel/` elaborates the frozen top and nine direct children,
the RTL0.2 logical ready/valid carrier bundles, `core_clk`,
`destructive_reset`, and the sole R1 external-memory carrier. It contains no
registers or mutable architectural state. The required opaque logical fields
have no deployment defaults: only the structural test supplies local values
needed to elaborate a finite carrier shape.

The no-model evidence is the Chisel structural test
`RouteAKVSubsystemTopSpec`; it checks the ten-module hierarchy in CHIRRTL, the
external top port names in in-memory SystemVerilog, the selected anchor widths,
and absence of sequential RTL. CIRCT may optimize inert child shells out of its
final SystemVerilog; that is why hierarchy is checked at the elaborated CHIRRTL
stage rather than by adding non-architectural logic to defeat optimization.

**RTL1.0.b verification binding infrastructure: complete.**
`hardware/route_a/chisel/src/test/resources/rtl1_0_verification_binding.json`
binds every one of the 15 frozen matrix records to its frozen skeleton owner,
one SVA-registry marker, its safety-guarantee or progress-fairness role, and
the one existing Python oracle association. The accompanying zero-port
SystemVerilog registry binds to `route_a_kv_subsystem_top`; it adds no design
behavior or assertion body. The Python
`RouteAScoreboardOracleBindingRegistry` exposes the exact frozen oracle path,
entry-point labels, observation description, and forbidden adapter rule without
dispatching an event or running a model.

At RTL1.0.b completion every safety body was explicitly
`owner_state_pending` and every progress body `owner_event_pending`. That was
required because RTL1.0.a had no owner state or event transitions to observe.
The registry proves binding inventory/ownership consistency only; it is not an
SVA/formal proof, Python-scoreboard execution, directed protocol test,
randomized scenario, or RTL functional pass. Consequently RTL1.0.b alone did
not authorize R1--R6 behavior.

## RTL1.1 progress

**RTL1.1 R1 core-memory wrapper: complete at module scope.**
`RouteACoreMemIfV1` replaces only the R1 inert shell with the selected
`core_mem_if_v1` transaction state: four live reads, one live write,
`(RID[2:0], incarnation[1:0])` live/retired identity discipline, ordered
512-bit fragments, fail-closed malformed or early-write-commit handling, and
one terminal removal. Its write commit reports payload durability only; it
does not create publication, page authority, a packed read, or any R3/R5
behavior.

`mem_init_done` is a module-local adapter acknowledgement. After destructive
reset, R1 will not accept or emit traffic until it is observed. The adapter
must suppress/drain pre-reset replies before acknowledging it; because the
adapter epoch is explicitly not a core-side wire, R1 cannot distinguish an
adapter-violating old response from a new response with the same numeric
identity after that acknowledgement. The still-inert top ties this local input
low until the lifecycle/reset owner phase integrates the handshake. Therefore
this is an R1 module pass, not a functional top-level Route-A pass.

The binding manifest now marks the three R1-owned safety records
`a_descriptor_unique_memory_path`, `a_reset_stale_exclusion`, and
`a_stale_response` as `owner_chisel_assert_bound`; all other safety and
progress records remain pending. The zero-port SVA registry remains only the
frozen top-level attachment; these three bodies are Chisel assertions, not an
SVA/formal proof. The frozen Python scoreboard association is still read-only
inventory binding, not an event-dispatch adapter or an RTL/Python equivalence
claim.

No-model ChiselSim directed tests cover reset-init gating, stalled read
fragment forwarding, terminal stale suppression, same-epoch identity reuse
rejection, the four-read bound, ordered write fragments, successful terminal
write commit, early-commit terminal fault, and pre-init stale response
suppression. They make no HBM controller, CDC, timing, bandwidth, PPA, model,
GPU, performance, or complete RTL-correctness claim.

## RTL1.2.0 progress

**RTL1.2.0 R2 semantic-carrier realization: complete.**
`analysis/rtl1_2_r2_semantic_carrier_contract.md` resolves the RTL1.0 opaque
candidate and source-delivery records into the existing-port R2 request,
predicate, response-association, and parameter boundary. It neither adds a
top-level channel nor chooses a physical queue/FIFO depth. RTL1.2 may now
implement the R2 owner behavior only against that carrier contract.

## RTL1.2 progress

**RTL1.2 R2 arbiter: complete at module scope.** `RouteACoreSideArbiter`
implements parameterized candidate storage, class-specific eligibility checks,
the frozen read rotation and ordinal/id selection, accepted-grant-only cursor
advance, a separate descriptor/write path, R1 response association, and one
transport reservation per live R1 identity. It does not implement source
owners, metadata publication, semantic-credit return, an HBM controller, or
top-level traffic integration. The existing top remains inert until its later
owner phases connect candidate producers and `mem_init_done`.

The binding registry marks `a_ready_low_nonmutation` and
`a_fifo_credit_losslessness` as `owner_chisel_assert_bound`; `p_credit_return`
remains an environment-fairness progress obligation because publication/source
credits belong to later R3/R5/R6 owners. ChiselSim directed tests cover
ineligible backpressure, stalled grant stability, accepted cursor advancement,
matched terminal routing, and separate descriptor terminal release. This is
no-model functional-module evidence only, not SVA/formal proof, controller,
timing, throughput, PPA, or end-to-end RTL correctness evidence.
