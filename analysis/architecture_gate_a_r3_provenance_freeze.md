# Gate-A R3 M2/P3 wrapper provenance freeze

## Status and boundary

**Status:** `r3_m2_p3_logical_wrapper_contract_complete; gate_a_still_blocked_on_r4_r6`.

This record freezes R3's logical M2/P3 wrapper contract and pure-software
event-level reference.  It neither selects a production SRAM macro, physical
port count, P3 banking, page-manager placement, HBM controller, timing/service
model, PPA result, or RTL implementation.  It runs no model/GPU workload and
does not alter an A4 artifact or frozen Route-A semantic.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `f32f4ee676702b43f915d4338332b0eca1fbae8fad994ccfbf53716d658ae71e` | Pre-RTL specification with R3 wrapper binding. |
| `analysis/architecture_gate_a_reviewer_01.md` | `9d7f2fff2ed090ea59a2c9f72533ad6fd3a110650ba214ef1f4194fc27492b84` | Reviewer disposition: R1--R3 closed; R4--R6 remain blockers. |
| `analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md` | `9ff80e9dfbe4a34a1485b4ccd146e80a4f761be5a318bc5cec6df4f452ff607c` | R1 memory durability/reset boundary consumed by R3. |
| `analysis/architecture_gate_a_r2_arbitration_dependency_contract.md` | `e83a75a73e946862ef17333a6b11f1d6a04e8c1dd5a28af02c03c1b598f23d42` | R2 eligibility predicates supplied by R3 stage ownership/completion. |
| `analysis/architecture_gate_a_r3_m2_p3_wrapper_contract.md` | `43529efefaf96e1a111ad66ae9b8efe1c59e00c221b014cc02fdf776c9fad62a` | Selected M2/P3 logical-port, ownership, fault, reset, and publication contract. |
| `analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` | `c7c40aab9e390fc46a9e48af18711dd7a61d6324006327dc822d99be343d81aa` | Finite 36-layer/eight-bank/one-packer anchor. |
| `kvpress/route_a_core_memory_reference.py` | `6f7edebf2ee64779d4bc625d48e39de42a79506b366b1afffc520df9ff6c1f09` | R1 core memory wrapper reference. |
| `kvpress/route_a_arbitration_reference.py` | `a3f71a0fc2b737fc7b0f2e041ef7a104f96a60d15da7a9960eab1caa3204e48a` | R2 dependency/issue reference. |
| `kvpress/route_a_m2_p3_reference.py` | `73d6e203d572019ddc6b621c1df2be1261b6f2616182412a386797b9a77bc5bb` | R3 M2/P3 event-level wrapper reference. |
| `tests/test_route_a_m2_p3_reference.py` | `67c321d0ca5c2b0dfa7d4a9b57eb6eb89cb4a3adbb7c83bf1b032048759e7fd8` | R3 directed wrapper/ownership/fault/reset tests. |

## Test binding

The following no-model command passed with `88 passed`:

```text
.venv/bin/python -m pytest -q \
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

This is pure-software executable architecture-contract evidence only.  It
makes no model/GPU, cycle/timing/throughput, controller, energy/PPA, RTL
correctness, or new-A4-DSE claim.
