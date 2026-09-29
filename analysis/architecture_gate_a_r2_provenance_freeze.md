# Gate-A R2 arbitration/dependency provenance freeze

## Status and boundary

**Status:** `r2_core_side_dependency_and_grant_contract_complete; gate_a_still_blocked_on_r3_r6`.

This record freezes the R2 core-side eligibility/dependency/issue contract and
its pure-software R1-integrated reference.  It does not select an external HBM
scheduler or controller, create a timing/service model, make a PPA claim, run
a model/GPU workload, alter A4 semantics, or authorize RTL.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `c8d67a4e97aa53e3cc8a2f5d54740a8d17ddae8ec822a894d63df2a4e2a5e227` | R1/R2 core-side transport, eligibility, and issue boundary. |
| `analysis/architecture_gate_a_reviewer_01.md` | `ff82f87909908900c42b4f9c2b657057503f33c907e1fffa3bc8bd4fa45f5996` | Reviewer disposition: R1/R2 closed; R3--R6 remain blockers. |
| `analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md` | `9ff80e9dfbe4a34a1485b4ccd146e80a4f761be5a318bc5cec6df4f452ff607c` | R1 core-memory boundary consumed by R2 grants. |
| `analysis/architecture_gate_a_r2_arbitration_dependency_contract.md` | `e83a75a73e946862ef17333a6b11f1d6a04e8c1dd5a28af02c03c1b598f23d42` | Selected R2 eligibility and deterministic grant contract. |
| `analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` | `c7c40aab9e390fc46a9e48af18711dd7a61d6324006327dc822d99be343d81aa` | Finite anchor read/write/source bounds. |
| `kvpress/route_a_core_memory_reference.py` | `6f7edebf2ee64779d4bc625d48e39de42a79506b366b1afffc520df9ff6c1f09` | R1 core-memory transaction reference. |
| `kvpress/route_a_arbitration_reference.py` | `a3f71a0fc2b737fc7b0f2e041ef7a104f96a60d15da7a9960eab1caa3204e48a` | R2 scoreboard and deterministic grant reference. |
| `tests/test_route_a_core_memory_reference.py` | `6c28799ab202eeaef3e04a2a9c5989e1b6fe096cb8ca9ba01dcd362274736e41` | R1 regression tests. |
| `tests/test_route_a_arbitration_reference.py` | `d20c944328667ce81b80657639dc5c4e836b17f217b83318661152566f3e953b` | R2 dependency, grant, fault, and no-mutation tests. |

## Test binding

The following no-model command passed with `78 passed`:

```text
.venv/bin/python -m pytest -q \
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

This is executable protocol/semantic evidence only.  Its deterministic
rotating grant is not an external-HBM arbitration, latency, throughput,
deadlock, bandwidth, energy, PPA, or RTL result.
