# RTL1-V provenance freeze

**Status:** `rtl1_v_verification_completion_complete`.

This record binds the RTL1-V assertion/fairness/scoreboard closure. All
evidence is no-model: it runs no LLM, GPU workload, A4 DSE, controller model,
numeric datapath, timing, throughput, PPA, or RTL formal proof.

## Bound artifacts

| SHA-256 | Artifact |
|---|---|
| `6fa4036e0cb1c15443dd7b037398732c7b2577c6a374aa90369ab5a1b4742365` | `analysis/rtl1_phase_contract.md` |
| `f0eb7f2efed8c9042f21e5025099451ec8f8c1447b41d916b8dab9eac05d3557` | `analysis/rtl1_v_verification_completion_contract.md` |
| `7c7b638568fdf132822029dd3749619f77a676433309ebb6d357dd10ad2ab74f` | `analysis/rtl1_v_scoreboard_event_schema.json` |
| `c3a159e8079d83fc2d654d0ca7182dc7d3ae39844132dfc97942eab8be6c0f7a` | `analysis/rtl_entry_scoreboard_oracle_manifest.json` |
| `c4fe02e61f389da774a41b3c046bfb73f306d56f61cd736f6756075a8458be09` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala` |
| `97932341d2d9a7f50c64f54d5e3fa69b36e6383fcd2d22661a84789df39a3b1c` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/integration/RouteAFairReclaimIntegrationSpec.scala` |
| `bd35f833ec0cee69bcf06d4b889b0936a90a3697be47061b0d7c384e8524718a` | `hardware/route_a/chisel/testbench/route_a_scoreboard_event_adapter.py` |
| `fbcca99898330c0f89985a30c5ed4e1bc3b191bb6aa61a4c74423a344f519237` | `hardware/route_a/chisel/src/test/resources/rtl1_0_verification_binding.json` |
| `167a7280aa6c036f2aa2fcca2493ae96964838e678f88187482e2d44776db6fe` | `tools/validate_rtl1_0_verification_binding.py` |

## Exact no-model checks

```bash
.venv/bin/python tools/validate_rtl1_0_verification_binding.py
.venv/bin/python tools/validate_rtl_entry_interface_manifest.py --require-interface-signals
.venv/bin/python tools/validate_rtl_entry_scoreboard_oracle.py
.venv/bin/python -m pytest \
  tests/test_rtl1_v_scoreboard_event_adapter.py \
  tests/test_rtl1_0_verification_binding.py \
  tests/test_rtl_entry_scoreboard_oracle.py -q

cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 sbt -batch \
  "testOnly kvpress.routea.r1.RouteACoreMemIfV1Spec \
  kvpress.routea.r2.RouteACoreSideArbiterSpec \
  kvpress.routea.r5.RouteAReclaimSpec \
  kvpress.routea.r6.RouteALifecycleAdapterSpec \
  kvpress.routea.integration.RouteAFairReclaimIntegrationSpec \
  kvpress.routea.structural.RouteAKVSubsystemTopSpec"
```

The ChiselSim bundle passed 21 tests. The Python bundle and validators are
re-run for this freeze. The fixed-seed composition uses seed `0x51A11`; it
injects only legal ready-low intervals and eventually releases the external
response/drain peers required by the progress assumptions.

## Disposition

RTL1-V closes the four review gaps: R5 durable invalidation/free association,
R6 authority-edge conservation without a second authority table, finite
fairness witnesses for all three progress records, and an executable
transaction adapter over the frozen Python references. It authorizes RTL2
production-dataflow planning and an initial event-emitting control slice.
It does **not** authorize a top-level end-to-end correctness claim, R4 numeric
RTL, a physical HBM controller, timing, PPA, or speedup claim.
