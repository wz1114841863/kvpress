# RTL1-I1 — init/drain behavioral composition provenance freeze

## Status and evidence boundary

**Status:** `complete_rtl1_i1_safe_start_empty_retire_composition`.

This freeze records the RTL1-I1 composition that binds the dedicated external
R1 reset-epoch acknowledgement and the named owner-local init/drain facts. It
is no-model, no-GPU, no-new-A4-DSE verification evidence. The ChiselSim tests
are functional ready/valid protocol checks only: they make no formal-proof,
cycle/latency/throughput, controller/CDC, numeric-datapath, payload-storage,
PPA, synthesis-signoff, or end-to-end Route-A correctness claim.

## Bound artifacts

| SHA-256 | Path | Role |
|---|---|---|
| `6c91b5759820e19d1be89385b054a245b0da6368a501e8e97af2d896550f13cb` | `analysis/architecture_spec.md` | Architecture reset/init boundary refinement. |
| `d971b21f3bce3ec7de46756a04fef4a1d07e4c0fe9570235ed09024bc0ee4758` | `analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md` | Dedicated external init acknowledgement. |
| `445b00f6410da976421eb7a3a9fd1da1d1610a9b341ad2bf44f1de17ecc2b684` | `analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md` | R6 named init/drain dependency. |
| `e693905a9e09f5193ab0799b8f93e7215d1f9a9c95ffd8c5dad088b3235d0413` | `analysis/rtl1_i1_init_drain_carrier_contract.md` | I1 carrier and behavioral closure contract. |
| `ba95edeca348ee0cfb7ed9aab517040ceb84e179c98ea74063435a3177dba887` | `analysis/rtl1_i1_interface_manifest.json` | I1 machine-readable composition manifest. |
| `25da1488187d99098ff459864577968f2d0dfd5b2a90cce64f43129809f4d85a` | `analysis/rtl_entry_interface_manifest.json` | Amended hierarchy/unique-owner manifest. |
| `b9b6bc2e433302de0d2ae7cb5770de05b64a56c27e51d07f37cdfd1fab9a45fb` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/interfaces/RouteAInterfaces.scala` | External init-ack carrier. |
| `d900698502556c9790ffee4847e54100591dd37ceb42dd22b162e204af9361d0` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/common/RouteACommonSkeletons.scala` | R1/R2/S2 local init/drain facts. |
| `b897997fa043ce44dfce21029bd5953ea317a0d17bc6d14f6b9eabcef65930b2` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala` | R3/R5/direct/R4/R6 local init/drain facts. |
| `3862b8c53754de615d3523411f5ca08800ad52fd8d74b66131df2698075ee91b` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAComponentStatusCollector.scala` | One-record lossless named-status collector. |
| `5b90b8fb2849e3f39d5b43ffa08d2e44e5d2c5e769527476e43f136f8d3ac39d` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala` | I1 top composition. |
| `eef5c95a9da06620b6b7107f6b03751683d3068e00739f100464d94c5b4b3594` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/integration/RouteAInitDrainIntegrationSpec.scala` | Collector and top directed ChiselSim. |
| `260ae77257bfd8d87eea94c497d56d06b889b3449c83078509a6a5f8a10fc9a0` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/r1/RouteACoreMemIfV1Spec.scala` | R1 test migration to external init-ack. |
| `fe048440e1175686b68f5bf9f5e8d0d146a1017f3024e939eff74455b3bc869d` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/r2/RouteACoreSideArbiterSpec.scala` | R2 drain-mode input initialization. |
| `db008a208b43866dda6580909cdcf845cdb4460a310f0ad2e96bfbef5b243de2` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/r3_r5/RouteAR3R5PublicationSpec.scala` | R3/R5 drain-mode input initialization. |
| `f4eef784a87cc3cb2fb0e1424e084ac6d9a5cd234bb43a563347aff0b8dafb28` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/r4/RouteAMergeBoundarySpec.scala` | R4 drain-mode input initialization. |
| `d43e49cd09adb85cb597741384b6ed510cabd57e19b3a88dd5eacb55683434ea` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/s2/RouteAS2DirectPendingSpec.scala` | S2/direct drain-mode input initialization. |

## Exact no-model preflight

```bash
.venv/bin/python tools/validate_rtl_entry_interface_manifest.py --require-interface-signals
.venv/bin/python -m pytest tests/test_rtl_entry_interface_manifest.py tests/test_rtl1_i_integration_manifest.py -q
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch "testOnly kvpress.routea.integration.RouteAComponentStatusCollectorSpec kvpress.routea.integration.RouteAInitDrainIntegrationSpec"
```

**Result:** PASS. The manifest validator passed; pytest reported `10 passed`;
the I1 ChiselSim command reported `3` directed tests passed. Existing R1--R6
module tests were recompiled against the new carrier ports. No model/GPU or
Route-A experiment was run.

## Frozen I1 disposition

The external adapter alone supplies `init_ack`; R1 alone converts it into the
named R1 init fact. The collector serializes the three init and eight drain
facts without becoming an authority owner. R2 quiesces new candidate intake at
retirement, and R1 drain cannot be accepted before both R2 drain partitions.
Thus an initialized, otherwise empty top can start one anchor session and
return its matching retirement acknowledgement only after the eight named
local-empty predicates reach R6.

I1 does **not** close admission context, non-contiguous per-record publication
membership, pending-to-packed authority observation, R2 delivery context,
source-instance/R4 completion, actual payload movement, fault recovery, or
R5 invalidation/reclaim/reuse. Those remain the ordered RTL1-I2--I4 scope.
