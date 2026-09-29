# Gate-A R5 page-manager/descriptor provenance freeze

## Status and boundary

**Status:** `r5_page_manager_descriptor_contract_complete; gate_a_still_blocked_on_r4_r6`.

This record freezes R5's selected logical packed-page descriptor, placement,
publication, and retirement/reclaim contract.  It is pure-software executable
architecture-contract evidence.  It neither selects a physical HBM controller,
address map, descriptor cache, SRAM macro, port count, timing/service model,
energy/PPA result, nor an RTL implementation.  It runs no model/GPU workload,
does not alter an A4 artifact, and does not reopen pruning, admission,
scheduling, or the existing atomic-publication semantics.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `88845290bc11b3864099ec429fea189b061c9d45cbb3a2e6598e8650ca3b8ce4` | Pre-RTL specification with R5 descriptor and retirement binding. |
| `analysis/architecture_gate_a_reviewer_01.md` | `a970fcdbbe6ae3791518a59ca9b2f0bc8822114fb0d52e14eb343218e79f7ed9` | Reviewer disposition: R1--R3/R5 closed; R4/R6 remain blockers. |
| `analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md` | `9ff80e9dfbe4a34a1485b4ccd146e80a4f761be5a318bc5cec6df4f452ff607c` | R1 durability, fragment, fault, reset, and response-suppression boundary consumed by R5. |
| `analysis/architecture_gate_a_r2_arbitration_dependency_contract.md` | `e83a75a73e946862ef17333a6b11f1d6a04e8c1dd5a28af02c03c1b598f23d42` | R2 data-plane grant order preserved by R5's separate maintenance client. |
| `analysis/architecture_gate_a_r3_m2_p3_wrapper_contract.md` | `43529efefaf96e1a111ad66ae9b8efe1c59e00c221b014cc02fdf776c9fad62a` | Existing M2/P3 publication action bound to R5 descriptor visibility. |
| `analysis/architecture_gate_a_r5_page_manager_descriptor_contract.md` | `86013516a4d55d077976ec607e10c506781945de56b412603ab66255977638f2` | Selected R5 storage, entry map, maintenance, and retirement contract. |
| `analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` | `c7c40aab9e390fc46a9e48af18711dd7a61d6324006327dc822d99be343d81aa` | Finite 32K x 1, 36-layer/eight-KV-head/page-pool anchor. |
| `kvpress/route_a_core_memory_reference.py` | `6f7edebf2ee64779d4bc625d48e39de42a79506b366b1afffc520df9ff6c1f09` | R1 identity/reset reference consumed for retirement/init binding. |
| `kvpress/route_a_arbitration_reference.py` | `a3f71a0fc2b737fc7b0f2e041ef7a104f96a60d15da7a9960eab1caa3204e48a` | R2 event-level dependency reference whose source classes remain unchanged. |
| `kvpress/route_a_m2_p3_reference.py` | `73d6e203d572019ddc6b621c1df2be1261b6f2616182412a386797b9a77bc5bb` | R3 event-level publication/fault/reset reference. |
| `kvpress/route_a_rtl_profile.py` | `77450775b2644c59264c0c835cd610a6127315ddf521bd04323a3055b7001c70` | A3 PageRef allocator, generation-wrap, and finite-anchor reference. |
| `kvpress/route_a_architecture_reference.py` | `e9d09596e05c32949735a8f040a1b57e5c06b7a25d250faae840b340ac14ff15` | A2 authority/atomic-publication reference used by the R5 integration test. |
| `kvpress/route_a_page_manager_reference.py` | `fabe8864cba606b7fa12363615d20b468079a101fddbcd85d5e49735a798fd33` | R5 event-level descriptor/page-manager reference. |
| `tests/test_route_a_page_manager_reference.py` | `746f81280377fbb31de48892a10b78a7523f52ba755b6b91dfd16461485971c4` | Directed R5 descriptor/publication/fault/retirement/reset tests. |
| `tests/test_route_a_rtl_profile.py` | `2b0669362bef2a03ba4c9449e4a6ec030a46bc9947df4afcbc52d1c8a36681a8` | A3 finite-profile and page-reuse checks. |
| `tests/test_route_a_architecture_reference.py` | `280d3a53f7c06cdbf43550d605821637c4720e3ce5e3db727d539657892f714e` | A2 authority and atomic-publication checks. |

## Test binding

The following exact no-model command passed with `97 passed in 3.95s`:

```text
.venv/bin/python -m pytest -q \
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

The tests establish only logical descriptor packing/address derivation,
private-to-published visibility, fail-closed maintenance faults, finite
maintenance ownership, retirement drain, invalidation-before-reuse, and reset
init ordering.  They make no model/GPU, cycle/timing/throughput, controller,
HBM-traffic/energy/PPA, RTL correctness, or new-A4-DSE claim.
