# Gate-A R6 top-level lifecycle provenance freeze

## Status and boundary

**Status:** `r6_top_level_lifecycle_contract_complete; reviewer_02_pending; gate_a_not_passed`.

This record freezes R6's generic lifecycle adapter, top-level ownership graph,
finite Qwen-anchor fields, reset/init prerequisites, and retirement-drain
dependency. It is pure-software executable architecture-contract evidence. It
selects no predictor interface, controller/FSM, physical port/macro, HBM
controller, timing/service model, energy/PPA result, or RTL implementation. It
runs no model/GPU workload, does not change an A4 artifact, and does not reopen
pruning, admission, scheduler, FIFO, ownership, or atomic-publication semantics.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `6953bcf71e8bc966e51e927b3b565712d4c34adb152785337d4682542e4e60c6` | Pre-RTL specification with R6 graph and adapter binding. |
| `analysis/architecture_gate_a_reviewer_01.md` | `c5d706a37ccd4c48e532f9e5fd9b508e5da56c8640891029e18dd9fe00f8ab39` | Closure record: R1--R6 complete, Reviewer 02 remains required. |
| `analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` | `c7c40aab9e390fc46a9e48af18711dd7a61d6324006327dc822d99be343d81aa` | Finite 32K x 1, 36-layer/eight-head, identity/retirement anchor. |
| `analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md` | `9ff80e9dfbe4a34a1485b4ccd146e80a4f761be5a318bc5cec6df4f452ff607c` | R1 memory/reset/stale-response owner in the R6 graph. |
| `analysis/architecture_gate_a_r2_arbitration_dependency_contract.md` | `e83a75a73e946862ef17333a6b11f1d6a04e8c1dd5a28af02c03c1b598f23d42` | R2 eligibility/order owner in the R6 graph. |
| `analysis/architecture_gate_a_r3_m2_p3_wrapper_contract.md` | `43529efefaf96e1a111ad66ae9b8efe1c59e00c221b014cc02fdf776c9fad62a` | R3 publication/P3/reset owner in the R6 graph. |
| `analysis/architecture_gate_a_r4_numeric_merge_contract.md` | `068372d0dd6893a2e7ac3250c26a18f76bb5368b20700f212eea97edb6d2bd86` | R4 finite merge/fault owner in the R6 graph. |
| `analysis/architecture_gate_a_r5_page_manager_descriptor_contract.md` | `86013516a4d55d077976ec607e10c506781945de56b412603ab66255977638f2` | R5 descriptor/reclaim/reset owner in the R6 graph. |
| `analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md` | `f557a15b45744b205f2ab0c4422677e5da1b01e5e8bac0e16080e2078c9e4cb7` | Selected generic lifecycle ports, graph, and drain contract. |
| `kvpress/route_a_architecture_reference.py` | `e9d09596e05c32949735a8f040a1b57e5c06b7a25d250faae840b340ac14ff15` | A2 authority/source-order reference preserved by R6. |
| `kvpress/route_a_core_memory_reference.py` | `6f7edebf2ee64779d4bc625d48e39de42a79506b366b1afffc520df9ff6c1f09` | R1 transaction identity type consumed by R6. |
| `kvpress/route_a_lifecycle_adapter_reference.py` | `aaa59c213da453b05991652b59e7cf5e98fc749abd71d114dda3a58c9f098a8d` | R6 event-level generic lifecycle/retirement reference. |
| `tests/test_route_a_architecture_reference.py` | `280d3a53f7c06cdbf43550d605821637c4720e3ce5e3db727d539657892f714e` | A2 authority/source-order tests. |
| `tests/test_route_a_lifecycle_adapter_reference.py` | `fcfd2462015faf1f21af267606a6b06e467f354a1deffd7737fde0df531cf826` | R6 generic-port, lifecycle, dispatch, reset, and drain tests. |

## Test binding

The following exact no-model command passed with `120 passed in 4.22s`:

```text
.venv/bin/python -m pytest -q \
  tests/test_route_a_lifecycle_adapter_reference.py \
  tests/test_route_a_merge_numeric_reference.py \
  tests/test_route_a_page_manager_reference.py \
  tests/test_route_a_m2_p3_reference.py \
  tests/test_route_a_arbitration_reference.py \
  tests/test_route_a_core_memory_reference.py \
  tests/test_route_a_rtl_profile.py \
  tests/test_route_a_architecture_reference.py \
  tests/test_kvzap_route_a4112b_external_storage_binding.py \
  tests/test_kvzap_route_a4120_metadata_interface_inventory.py \
  tests/test_kvzap_route_a4121_metadata_macro_envelope.py \
  tests/test_kvzap_route_a4122_cache_ownership.py \
  tests/test_kvzap_route_a4122_metadata_cycle_energy.py \
  tests/test_kvzap_route_a4131_payload_organization.py \
  tests/test_kvzap_route_a4133_packed_kv_hbm_realization.py \
  tests/test_kvzap_route_a4134_page_source_reuse_interface.py \
  tests/test_kvzap_route_a4135_target_payload_service_cost.py \
  tests/test_kvzap_route_a4140_allhead_gate.py \
  tests/test_kvzap_route_a4140_workload_aligned_metadata_cost.py \
  tests/test_kvzap_route_a4141_accounted_net_benefit_ledger.py
```

The tests establish only generic finite port inventory, score-free frontend
boundary, event-level lifecycle/authority preservation, canonical dispatch,
identity lifetime, reset/init, and retirement-drain ordering. They make no
model/GPU, cycle/timing/throughput, controller/HBM, energy/PPA, RTL correctness,
accuracy, or new-A4-DSE claim.
