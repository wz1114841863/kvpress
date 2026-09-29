# Gate-A R1 core memory-wrapper provenance freeze

## Status and boundary

**Status:** `r1_core_mem_if_v1_complete; gate_a_still_blocked_on_r2_r6`.

This record freezes the R1 core-side memory-wrapper/clock/reset contract and
its pure-software transaction reference.  It does not authorize RTL, select an
HBM controller/PHY/CDC implementation, establish timing or throughput, make a
PPA claim, run a model/GPU workload, or add an A4 DSE.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `78b933057b4ada629750d71404d1721352541afaf1deadcaaee48b522ffb8df1` | R1 core-memory transport and reset boundary. |
| `analysis/architecture_gate_a_reviewer_01.md` | `6766c2d66971211570d83d7bf029562ef996f25108ef72a0392a6128c496bd4e` | Reviewer disposition: R1 closed; R2--R6 remain blockers. |
| `analysis/architecture_gate_a_r1_core_memory_wrapper_contract.md` | `9ff80e9dfbe4a34a1485b4ccd146e80a4f761be5a318bc5cec6df4f452ff607c` | Selected `core_mem_if_v1` contract. |
| `analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` | `c7c40aab9e390fc46a9e48af18711dd7a61d6324006327dc822d99be343d81aa` | Finite anchor bounds consumed by R1. |
| `kvpress/route_a_core_memory_reference.py` | `6f7edebf2ee64779d4bc625d48e39de42a79506b366b1afffc520df9ff6c1f09` | Event-level core-memory reference. |
| `tests/test_route_a_core_memory_reference.py` | `6c28799ab202eeaef3e04a2a9c5989e1b6fe096cb8ca9ba01dcd362274736e41` | Directed R1 ordering/fault/reset/backpressure tests. |
| `kvpress/route_a_architecture_reference.py` | `e9d09596e05c32949735a8f040a1b57e5c06b7a25d250faae840b340ac14ff15` | A2 authority/publication reference consumed by the durable-only cross-check. |
| `tests/test_route_a_architecture_reference.py` | `280d3a53f7c06cdbf43550d605821637c4720e3ce5e3db727d539657892f714e` | A2 semantic regression tests. |

## Test binding

The following no-model command passed with `76 passed`:

```text
.venv/bin/python -m pytest -q \
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

The result is only executable protocol/semantic evidence.  It contains no HBM
command/timing/controller implementation, numeric merge closure, PPA evidence,
or RTL execution.
