# Full-KV baseline legal-path audit and first dual-DUT Chisel work package

**Status:** Targeted source audit complete on 2026-10-16.  MBR.0, MBR.1, and
MBR.1-A are approved and are not reopened here.  This record resolves only
the three required Full-KV baseline paths and names the first bounded RTL work
package.  It does not modify RTL, select a wrapper/macro/numeric design, run
DC/CACTI, or make a physical/PPA/performance claim.

## Approval record and scope

External technical review returned `PASS with minor corrections` for MBR.0,
MBR.1, and MBR.1-A; the user explicitly approved MBR.1 fairness planning and
MBR.1-A implementation-preparation on 2026-10-16.  The only pending decision
is whether to authorize the concrete Chisel work package below.  No further
MBR review or new overall planning phase is required.

## Targeted source finding

The existing common transaction path has useful Full-KV hooks, but it does
**not** implement any of the three required end-to-end Full-KV ownership
paths.  The result is therefore **insufficient for direct integration**:
creating a baseline by tying off Route-A paths would be semantically false and
would allow optimization to undercount active control.

| Required path | Existing reusable portion | Missing legal owner/interface | Result |
|---|---|---|---|
| 1. Full-KV read request producer → R2/R1 | `RouteACoreSideArbiter` accepts `r2S2FullClassCode` as an ordinary read class and applies common read predicates; `RouteADeliveryContextRegistry` accepts `S2FullFill`; `RouteAReadIssueCandidateAdapter` can transport a generic non-hot read descriptor. | No `FullKVReadWork`/producer exists. `RouteAPackedS2ReadProducer` always emits packed class, packed source kind, a `PageRef`, and `requires_sidecar = true`. Reusing it would relabel Full-KV as packed. | **Open.** |
| 2. Memory response → S2 `READY` | `RouteACoreMemIfV1` preserves matching R1 responses; R2 records the outstanding candidate; registry resolution and `RouteATypedDeliveryRouter` already recognize `S2FullFill`. | `RouteAReadEndpointDemultiplexer` has P3/direct/packed/sidecar outputs only, no `S2FullFill` output/endpoint. `RouteAS2GqaSourceWrapper` stores `PageRef` and accepts/emits only packed source identity for lease, commits, release, and observation. | **Open.** |
| 3. Source completion → GQA consumers → terminal/retire | The Route-A implementation proves the desired individual concepts: S2 waits for four commits, R6 emits one terminal after consumer completion, and R1/R2 reset/stale rules are available. | `RouteASourcePlanBinder`, `RouteALifecycleAdapter`, `RouteASourceServicePacketAdapter`, and `RouteASourceCommitDemultiplexer` hard-code the three Route-A source kinds `hot/pending/packed`. The frozen Route-A plan has three presence bits and no Full-KV bit; Full-KV cannot lawfully enter the Route-A cross-source R4 merge path. | **Open.** |

Evidence locations are intentionally narrow:

- `hardware/route_a/chisel/src/main/scala/kvpress/routea/common/RouteACommonSkeletons.scala`:
  registry Full-KV target acceptance (31--40), R2 Full-KV read eligibility
  (533--587), generic read candidate adapter (752--792), typed
  `S2FullFill` routing (1463--1469), and the missing Full-KV demux output
  (1527--1551).
- The same file's S2 wrapper fixes packed identity at its lease/commit/release
  points (251--252, 433--453, 471--480); its source-service adapter and commit
  demux have exactly hot/pending/packed ports (1854--1925, 2248--2279).
- `hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala`
  fixes source-plan identity to those three kinds (307--310, 609--662).
- `hardware/route_a/chisel/src/main/scala/kvpress/routea/interfaces/RouteAInterfaces.scala`
  defines only `Hot`, `Pending`, and `Packed` (480--484) and says the
  `ReadIssueDescriptor` source vocabulary is canonical Route-A (614--635).

This is not a reason to extend Route-A's frozen source-plan vocabulary.  The
Full-KV baseline needs a **baseline-local** path, so it cannot alter the
hot/pending/packed contract, source-presence width, Route-A R4 merge behavior,
or Route-A atomic-publication semantics.

## First concrete dual-DUT Chisel integration work package

**Work-package ID:** `dual_measurement_dut_w0_full_kv_legal_path`.

This is the smallest authorized implementation candidate after a user says to
start RTL.  It creates a real Full-KV path beside the existing Route-A path;
it does not implement an HBM controller, storage macro, attention PE, R4
numeric pipeline, DC, CACTI, or a new scheduler.

### Files to add

| File | Minimal responsibility |
|---|---|
| `hardware/route_a/chisel/src/main/scala/kvpress/routea/baseline/FullKVMeasurementInterfaces.scala` | Baseline-local `FullKVReadWork`, fill association, source instance, payload/terminal, consumer-commit, source-complete, and terminal/retire bundles. They use the existing transaction identity and core-memory carrier but do **not** extend `RouteASourceKind`, Route-A source presence, or `PageRef`. |
| `hardware/route_a/chisel/src/main/scala/kvpress/routea/baseline/FullKVReadPath.scala` | `FullKVReadProducer`, a baseline-local delivery-context allocation bridge, and `FullKVS2ReadEndpoint`. The producer owns an accepted Full-KV work-to-`r2S2FullClassCode` request; the bridge binds the existing registry before R2; the endpoint alone converts a matching resolved R1 response to Full-KV S2 payload/terminal carriers. |
| `hardware/route_a/chisel/src/main/scala/kvpress/routea/baseline/FullKVS2Completion.scala` | `FullKVS2GqaSourceWrapper` and `FullKVTerminalRetireAdapter`. The wrapper has the same two-slot/fill/READY/four-consumer/release semantic contract but no sidecar/PageRef or packed identity. The terminal adapter accepts exactly one completed Full-KV source after four commits and drives its baseline terminal/retire association without entering Route-A cross-source R4 merge. |
| `hardware/route_a/chisel/src/main/scala/kvpress/routea/top/FullKVMeasurementDut.scala` | New baseline DUT composition. It uses existing `RouteACoreSideArbiter`, `RouteACoreMemIfV1`, `RouteADeliveryContextRegistry`, and `RouteATypedDeliveryRouter` at their existing common interfaces, plus the new baseline-local owners above. |
| `hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAMeasurementDut.scala` | New Route-A DUT composition; preserve the C3/C4 owner path and replace its measurement-scope inactive ties with named legal owner or explicit outer contract ports. Do **not** modify `RouteAKVSubsystemTop`, which remains the historical composition skeleton. |
| `hardware/route_a/chisel/src/test/scala/kvpress/routea/FullKVMeasurementDutSpec.scala` | Positive and fail-closed Full-KV path regression. |
| `hardware/route_a/chisel/src/test/scala/kvpress/routea/DualMeasurementDutStructuralSpec.scala` | Both DUTs: no named `StructuralTieOff`/forced/testbench producer on included contours, matching `core_mem_if_v1` init/reset semantics, and no inactive-only Full-KV route. |

### Exact connections

```text
Full-KV
  FullKVReadWork (named external/full-KV owner contract)
    -> FullKVReadProducer
    -> FullKVDeliveryContextBridge
    -> RouteACoreSideArbiter.read_candidate_in
    -> RouteACoreMemIfV1 -> external core_mem_if_v1
    -> RouteACoreSideArbiter.core_mem_rsp_in
    -> RouteADeliveryContextRegistry.resolve_in/resolved_out
    -> RouteATypedDeliveryRouter.read_fragment_out
    -> FullKVS2ReadEndpoint
    -> FullKVS2GqaSourceWrapper FILL -> READY
    -> named outer source-partial boundary (one Full-KV source only)
    -> four Full-KV consumer commits
    -> FullKVS2 release -> FullKVTerminalRetireAdapter
    -> attention terminal / runtime retire acknowledgement

Route-A
  existing R3/R5 packed association -> packed producer/registry/R2/R1
    -> typed packed endpoint -> existing S2 READY
    -> existing outer source-partial and R4 reference boundaries
    -> four commits -> existing R6 terminal -> R5/R6 reclaim/retire
```

`FullKVReadWork` must enter through a named non-test owner contract.  It is not
a scheduler grant: it carries an already-selected causal Full-KV read identity,
opaque external-memory handle, expected fragment count, S2 slot association,
and existing R2 eligibility/ordering facts.  The implementation may not derive
any of these from a response or import them from a Route-A packed association.

### Required regressions for W0

1. Full-KV positive: accepted work produces exactly one `r2S2FullClassCode`
   R1 read; matching response fragments reach `READY` only after the final
   matching terminal; no sidecar transaction occurs.
2. Full-KV fail-closed: stale/reset-old identity, wrong fragment/order, wrong
   slot/generation, response fault, duplicate consumer commit, and early
   release cannot yield `READY`, a terminal success, or retire acknowledgement.
3. Full-KV completion: exactly four legal consumers commit; one source release
   yields one terminal and then one matching retirement acknowledgement.  No
   Route-A R4 merge work or source-presence bit is fabricated.
4. Route-A non-regression: C3/C4 functional success/replay/negative witnesses,
   no-early-read, atomic publication, and reclaim checks remain unchanged.
5. Structural parity: both DUTs expose the same `core_mem_if_v1` reset/init
   interface; included common control outputs are live or fail closed, never
   retained through a tie-off.  This is a structural/functional check only,
   not a cost or PPA result.

## Authorization boundary

W0 is ready for a direct user authorization to implement its Chisel files.
If approved, implementation begins with the baseline-local interfaces and
Full-KV path test, then composes the two measurement DUTs.  DC/CACTI, wrapper
port selection, macro selection, R4 arithmetic implementation, controller
work, and numerical cost/PPA conclusions remain outside W0.

## W0 implementation record (2026-10-16, in progress)

The first implementation batch adds the baseline-local Full-KV carriers,
Full-KV producer/context/endpoint/S2/four-consumer/terminal-retire controls,
and `FullKVMeasurementDut`.  Its no-model elaboration smoke test and a
directed transaction regression pass: a held `core_mem_if_v1` request is
checked before release, only a matching response reaches `READY`, four distinct
consumer commits precede terminal/retire, and stale response plus duplicate
commit cases fail closed.  The second batch adds an independent
`RouteAMeasurementDut` packed-read contour with named R3/R5 authorization,
common-R2/R1, typed-delivery, S2, sidecar, consumer, and terminal/reclaim
boundary ports. It neither instantiates the historical composition skeleton
nor contains a structural tie-off helper; its dual-DUT elaboration regression
passes. This is a **bounded, not same-instance C3/C4-complete** Route-A
contour: R3/R5 authorization and terminal/reclaim remain explicit outer owner
boundaries, rather than being replaced by fixture-generated events or a second
R6. Therefore W0 is not complete under its original “preserve C3/C4 owner
path” criterion. This is still functional integration evidence only: no DC,
CACTI, macro, controller, numeric, timing, throughput, area, or energy work
was run or implied.
