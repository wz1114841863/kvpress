# RTL1-I3 — delivery/source/R6 composition provenance freeze

## Status and evidence boundary

**Status:** `complete_rtl1_i3_delivery_source_and_r6_completion_composition`.

This freeze records only the bounded RTL1-I3 control association: opaque R2
delivery-context preservation, exact R4 source-instance return, four-consumer
owner-local release, and finite R6 planned-source completion before the
already-frozen merge/terminal boundary. It is pure synthesizable control and
directed ChiselSim protocol evidence. It makes no model/GPU, new-A4-DSE,
payload/HBM movement, source-mux/scheduler, numeric-datapath, formal-proof,
cycle/latency/throughput, PPA, synthesis-signoff, or end-to-end Route-A
correctness claim.

## Bound artifacts

| SHA-256 | Path | Role |
|---|---|---|
| `76a5ad3ca9b5e15f400960ecf901ea12993370f69d8199458d207f57c2fadf12` | `analysis/rtl1_i_cross_owner_integration_contract.md` | Frozen I0 permitted associations and prohibitions. |
| `1af5df17ea6e7c51398fd60d9a15acb2f3e13cddaaec7f0d9f3a732e5e841ac0` | `analysis/rtl1_i3_delivery_source_contract.md` | I3 semantic, ownership, and implementation boundary. |
| `3a73b082a621c22966ffab1c69c9de8833538a2c8560a8d0ced8c05ea966b9d1` | `analysis/rtl1_i3_interface_manifest.json` | I3 machine-readable carrier manifest. |
| `da2ff0af2627a981fcadc19e01433c0f231c39b67008a34cb1c70a1b4b5857c1` | `analysis/rtl_entry_interface_manifest.json` | Amended cross-owner interface inventory. |
| `7e166a4b26dc1acffd0b6d070e4f5924277924e7bf67e6edb2ad802c8626e5ef` | `analysis/rtl_entry_port_parameter_contract.md` | Matching rendered port matrix. |
| `c8f8fa3ecb6e187e5108ab355c809acd4a0b937b51952112e22b355fb58e8e05` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/interfaces/RouteAInterfaces.scala` | Source-instance and completion-plan carriers. |
| `0e43207012caaa36b91eab71e0b67f7c6ab22a599d75da6f2b77763fd4a5518c` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala` | R6 planned-release/merge association and existing R4 terminal intake. |
| `4ddf7faaeaba5386e197a627cc5e7cfee1517852ab1df90cfda7a47ca330a997` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/common/RouteACommonSkeletons.scala` | Hot/S2/direct exact-instance four-consumer ownership. |
| `cbcd83ed5816ea56d7d80ccade7f81798275f21bcdef2ee0f08793e18c94eadb` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala` | Commit demultiplex and per-owner release-to-R6 wiring. |
| `443588d1256a5ffd4bc287e71dc45ea1adf293500a9b04bd90f652798d456b61` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/r6/RouteASourceCompletionPlanSpec.scala` | All-mask/stale-generation and hot--R4--R6 fault composition tests. |

## Exact no-model preflight

```bash
.venv/bin/python tools/validate_rtl_entry_interface_manifest.py --require-interface-signals
.venv/bin/python -m pytest tests/test_rtl_entry_interface_manifest.py tests/test_rtl1_i_integration_manifest.py -q
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch "testOnly kvpress.routea.r2.RouteACoreSideArbiterSpec kvpress.routea.s2.RouteAS2DirectPendingSpec kvpress.routea.s2.RouteAHotSourcePathSpec kvpress.routea.r4.RouteAMergeBoundarySpec kvpress.routea.r6.RouteALifecycleAdapterSpec kvpress.routea.r6.RouteASourceCompletionPlanSpec kvpress.routea.integration.RouteAAdmissionPublicationIntegrationSpec kvpress.routea.structural.RouteAKVSubsystemTopSpec"
```

**Result:** PASS. The manifest validator passed; Python pytest reported `10
passed`; the directed ChiselSim command reported `21` tests passed across `8`
suites. No model, GPU workload, or Route-A DSE ran.

## Frozen I3 disposition

R2's `delivery_context_ref` is preserved but not decoded. R4 consumes and
returns an exact source-instance sideband without altering its 128-bit header.
Hot, direct-pending, and S2 remain the sole source owners and release only
after their four distinct matching consumer commits. R6 alone holds the finite
expected/released association for a live attention identity; it creates the
existing merge request only when every planned source has released. A delayed
or stale generation cannot satisfy that association. The existing R4 numeric
fault then follows the sole R6 terminal association.

I3 does not supply a production source-plan/packet ingress, source payload,
R2-to-source delivery adapter, P3/reclaim producer, numeric implementation,
or system-level end-to-end proof. Those remain later reviewed integration and
realization work.
