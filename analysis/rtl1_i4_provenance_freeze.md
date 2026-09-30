# RTL1-I4 — reclaim control composition provenance freeze

## Status and evidence boundary

**Status:** `complete_rtl1_i4_r5_reclaim_r2_r1_r6_control_composition`.

This freeze binds only the I4 synthesizable control composition: R6's
identity-bearing two-pass retirement permit, R5's complete logical 64-B
descriptor-line invalidation image, R2's permit-gated descriptor ingress, and
the existing sole R1 write request/data/terminal route. It is pure control and
directed ChiselSim evidence. It makes no model/GPU, new-A4-DSE, payload/HBM
movement, descriptor-cache/read/RMW, scheduler, numeric datapath, formal
proof, cycle/latency/throughput, PPA, synthesis-signoff, or end-to-end Route-A
correctness claim.

## Bound artifacts

| SHA-256 | Path | Role |
|---|---|---|
| `f3852d5393b7c9e4df88dd2114aab450814b2128e37ce6d6baba2dcd9c34ee11` | `analysis/rtl1_i4_reclaim_contract.md` | Frozen two-pass reclaim semantics and exclusions. |
| `e02be7e94ef7edb019616400732914fd6f7c193cdefbbe3e1a5f484ca0229987` | `analysis/rtl1_i4_interface_manifest.json` | Machine-readable I4 carrier contract. |
| `473f856b2ee13ff375dc6f4d67f61ae117f54ce9f1b106afa2cb742546a4dc33` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/interfaces/RouteAInterfaces.scala` | Explicit identity-bearing `ReclaimPermit` carrier. |
| `0244923124e9d0322e62d3ec39036634a0b0bf03d87b00cc60fd35b049a163a3` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/common/RouteACommonSkeletons.scala` | R2 permit gating and R1 selected finite-reuse control. |
| `d0e68b58fc40eac0799484d56f73ebd4fc8c879f07e3f9c40bb9fe15563f1175` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala` | R6 permit/final-drain state, permit ready-low stability, and R5 line invalidation state. |
| `6b83963f747ad3f32c379df0bed30a84468fe891d9493cd9f0b3aea3f47ee329` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAComponentStatusCollector.scala` | Suppressed/replayed R1 and R2-descriptor drain facts. |
| `6108ba2914d39cafa3847711f6227301bee0e24c4c5494ae053ad011d43d2c55` | `hardware/route_a/chisel/src/main/scala/kvpress/routea/top/RouteAKVSubsystemTop.scala` | R6/R5/R2/R1 composition wiring. |
| `9765c1e3bdb102ce69688eb051d6febf09ffbc31dbec10e646f7612ff86b37e8` | `hardware/route_a/chisel/src/test/scala/kvpress/routea/r5/RouteAReclaimSpec.scala` | Success, ready-low, single/multi-lane line images, and fault/no-free tests. |

## Exact no-model preflight

```bash
.venv/bin/python tools/validate_rtl_entry_interface_manifest.py --require-interface-signals
.venv/bin/python -m pytest tests/test_rtl_entry_interface_manifest.py tests/test_rtl1_i_integration_manifest.py -q
cd hardware/route_a/chisel
sbt -batch "testOnly kvpress.routea.r1.RouteACoreMemIfV1Spec kvpress.routea.r2.RouteACoreSideArbiterSpec kvpress.routea.r5.RouteAReclaimSpec kvpress.routea.r6.RouteALifecycleAdapterSpec kvpress.routea.structural.RouteAKVSubsystemTopSpec"
```

**Result:** PASS. The interface-manifest validator passed; Python pytest
reported `10 passed`; the directed ChiselSim suites reported `18` passed tests
across five suites. No model, GPU workload, Route-A DSE, timing, or PPA run.

## Frozen I4 disposition

R6 first collects the seven non-R5 drain facts, issues exactly one
identity-bearing permit, clears its pre-reclaim R1/R2-descriptor facts, then
requires R5 completion and fresh final R2-descriptor/R1 facts before its sole
retirement ack. R5 generates only a logical complete 512-bit descriptor line,
with allocated lanes written FREE/next-generation and nonparticipants left
FREE/current-generation. R2 remains the only core-side R1 issuer, R1 remains
the only external-memory carrier, and an R1 fault leaves the line allocated.

The fixed finite identity format cannot distinguish an old response after the
same numeric identity wraps. As selected by A3, the external environment must
provide no-old-response/wrap quiescence before that post-terminal reuse; I4
does not invent a wider identity or alter outstanding bounds.
