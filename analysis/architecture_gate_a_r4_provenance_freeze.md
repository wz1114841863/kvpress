# Gate-A R4 finite numeric merge provenance freeze

## Status and boundary

**Status:** `r4_finite_numeric_merge_contract_complete; gate_a_still_blocked_on_r6`.

This record freezes R4's binary32 partial/result packet boundary, canonical
source order, A2 comparison relation, normalization guard, and fail-closed
numeric disposition. It is pure-software executable architecture-contract
evidence. It selects no exp unit, internal arithmetic precision, pipeline,
timing/service model, storage macro, controller, energy/PPA result, or RTL.
It runs no model/GPU workload, changes no A4 artifact, and does not reopen
pruning, admission, scheduler, FIFO, ownership, or atomic-publication semantics.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `65720800f10d40d3b6c6aadf77e5e1c2f1e42d5358240573aca651900765801f` | Pre-RTL specification with R4 numeric interface binding. |
| `analysis/architecture_gate_a_reviewer_01.md` | `da037b09adcf3071a8c279a5eb5305f72050993908bbcf94491709a3b7217c46` | Reviewer disposition: R1--R5 closed; R6 remains the blocker. |
| `analysis/architecture_gate_a2_executable_contract.md` | `0f0a786a1a84997022c37bde683f3fa4bb79daffd24e2f9781244f049b9553fd` | A2 mathematical source-order and normalization reference boundary. |
| `analysis/route_a4134_page_source_reuse_interface_contract.md` | `6e750d68cc1490d6c43f0a38fb2d1409ebf0e4d4ab104f082491956071178d61` | A4.13.4 four-consumer FP32 partial-state interface source. |
| `analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` | `c7c40aab9e390fc46a9e48af18711dd7a61d6324006327dc822d99be343d81aa` | Finite one-group/four-consumer Qwen-anchor profile. |
| `analysis/architecture_gate_a_r4_numeric_merge_contract.md` | `068372d0dd6893a2e7ac3250c26a18f76bb5368b20700f212eea97edb6d2bd86` | Selected R4 format, comparison, and fault contract. |
| `kvpress/route_a_architecture_reference.py` | `e9d09596e05c32949735a8f040a1b57e5c06b7a25d250faae840b340ac14ff15` | A2 mathematical merge reference consumed by R4 comparison. |
| `kvpress/route_a_merge_numeric_reference.py` | `af6add96618a1bb48169140dabd038c5932251d62a63fe0ac6ea0c65c5ae31f6` | R4 binary32 packet, merge, fault, and A2-comparison reference. |
| `tests/test_route_a_architecture_reference.py` | `280d3a53f7c06cdbf43550d605821637c4720e3ce5e3db727d539657892f714e` | A2 source-order/normalization executable tests. |
| `tests/test_route_a_merge_numeric_reference.py` | `8b8660ec3e7fd2496a1c06fb4657567aefc76f09353fa3688f241061ecd0ad99` | R4 packet, all-subset, fault, comparison, and fixed-seed tests. |

## Test binding

The following exact no-model command passed with `112 passed in 3.91s`:

```text
.venv/bin/python -m pytest -q \
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

The tests establish only finite packet encoding, canonical binary32
mathematical semantics, A2 comparison, normalization preconditions, and
fail-closed numeric exceptions. They make no model/GPU, cycle/timing/throughput,
controller/HBM, energy/PPA, RTL correctness, accuracy, or new-A4-DSE claim.
