# RTL1-I2 — admission/publication composition provenance freeze

## Status and evidence boundary

**Status:** `complete_rtl1_i2_admission_publication_composition`.

This freeze records the R6--R3 retained-record association and post-publication
observation closure.  It is pure Chisel control-contract evidence: no model,
GPU, new A4 DSE, HBM/payload movement, physical P3/M2 macro, controller,
timing, throughput, PPA, formal proof, or end-to-end Route-A correctness claim
is made.  The test-only composition harness exposes later-owner P3/M2 ingress
only as directed stimulus; it is not a production data-path implementation.

## Bound artifacts

| SHA-256 | Path | Role |
|---|---|---|
| `76a5ad3ca9b5e15f400960ecf901ea12993370f69d8199458d207f57c2fadf12` | `analysis/rtl1_i_cross_owner_integration_contract.md` | Frozen I0 cross-owner rules. |
| `1dab315147788137a851cea349997094cc3dd8314181c40a0c82600fc65568e9` | `analysis/rtl1_i2_admission_publication_contract.md` | I2 semantic and implementation boundary. |
| `32f8396337eebef1376379a55d4a94bf6a35bca658a4cc62de52c0f86fbdcf75` | `analysis/rtl1_i2_interface_manifest.json` | I2 machine-readable carrier contract. |
| `bcd7cdfa3c802463082ec6b34774e204ab4ead2403a14caa620989f9c39de550` | `analysis/rtl_entry_interface_manifest.json` | Amended frontend field binding. |
| `9b11c0ff72616000a73c3d0804f08be94e0524eea9916395a7414abeeecc3ef6` | `analysis/rtl_entry_port_parameter_contract.md` | Matching reviewed Markdown matrix. |
| `3f496842f9ee09f9043070da4f09867f846ba732a7e78b60118f883ffd6cab8a` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/interfaces/RouteAInterfaces.scala` | Immutable context and observation carriers. |
| `445d087727324fbf6c626bc0a2dcc724fc690c1b9b88942fcc30332c8b69d3b8` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/common/RouteACommonSkeletons.scala` | Control-only hot acknowledgement. |
| `40ff980dd775da33302e79fe4e737f124622d010fb7886bae9502a6fb5660127` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala` | R6 staging and R3 membership/publication logic. |
| `7890cfde2b2fde92cc684f8ca7048ecf5d71ecbecb7fbfd301229663cf0203ea` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala` | Production R6--R3--R6 carrier wiring. |
| `14684703850c9eadb1d89de4023d039f30b7f96aa1cdc3b82450167ae847ee3c` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/r3_r5/RouteAR3R5PublicationSpec.scala` | Explicit non-contiguous/fault/atomic-visibility tests. |
| `cacf437ea04503664249bef97f204f336353d959ea3216d8e97ef13082042433` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/r6/RouteALifecycleAdapterSpec.scala` | R6 carrier-field test migration. |
| `2a4cb9d34b4a34a9a9828955917c9ffbe2d01645fd080735b451e592104a69d7` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/integration/RouteAAdmissionPublicationIntegrationSpec.scala` | R6--R3 composition-harness test. |

## Exact no-model preflight

```bash
.venv/bin/python tools/validate_rtl_entry_interface_manifest.py --require-interface-signals
.venv/bin/python -m pytest tests/test_rtl_entry_interface_manifest.py tests/test_rtl1_i_integration_manifest.py -q
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch "testOnly kvpress.routea.r3_r5.RouteAR3R5PublicationSpec"
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch "testOnly kvpress.routea.r6.RouteALifecycleAdapterSpec kvpress.routea.structural.RouteAKVSubsystemTopSpec"
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch "testOnly kvpress.routea.integration.RouteAAdmissionPublicationIntegrationSpec"
```

**Result:** PASS. The manifest validator passed; Python pytest reported `10
passed`; directed ChiselSim reported `5`, `7`, and `1` tests passed,
respectively.  No model/GPU workload or Route-A DSE ran.

## Frozen I2 disposition

An accepted RETAIN maturity can cross R6 into R3 only as an immutable, exact
record context paired with its matching `hot -> pending` transition.  R3 holds
explicit, non-contiguous members bounded by 64, blocks publication until every
member and pre-existing durability prerequisite is present, and reports each
member as `pending -> packed` only after the one existing atomic publication
acknowledgement.  It does not introduce a second commit or authority owner.

I2 does not close the top-level P3 claim/payload/metadata producer, R2/R1
delivery context, source/R4 completion, R5 invalidation/reuse, full global
authority/reclaim conservation, numeric realization, or physical macro and
controller decisions.  Those remain later RTL1-I substeps and Gate-B work.
