# Gate-A3 refinement provenance freeze

## Status and boundary

**Status:** `a3_finite_rtl_boundary_profile_complete`.  This freeze records
only the pure-software A3 parameter/interface refinement and its no-model
validation.  It does not pass Gate A, authorize RTL, select a physical HBM
controller/macro, make cycle/timing/throughput/PPA claims, or reopen any A4
DSE or Route-A semantic decision.

The older `architecture_gate_a3_plan_provenance.md` and
`architecture_gate_a3_verification_provenance.md` remain historical snapshots;
this record binds the later selected anchor profile without rewriting them.

## Selected anchor

`rtl_entry_qwen3_8b_32k_s1_v1` is an engineering anchor instantiation only:
32,768 context tokens, one concurrent sequence, a shared 5-GiB cold-KV HBM
address pool, one pending endpoint, one pack engine, one active KV-head group,
and 512-bit/64-B core fragments.  It uses a keep-all cold-record capacity
guard rather than observed workload compression.  The profile schema has an
abstract retention-KV field vocabulary, but its evidence scope remains only
the Qwen3-8B Route-A anchor.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `a490c40a7033dcd0b499de924712245d7806b76487351266dd66a7d75e9a1b76` | Updated pre-RTL interface boundary and selected A3 anchor. |
| `analysis/architecture_gate_a3_plan.md` | `490ae050e5c676eedcb76f8a36eda7f64b75076ee6faf833807e2ba157ab2dfb` | Parameter derivation, shared-pool, and ownership closure. |
| `analysis/architecture_gate_a3_verification_small_v1.json` | `67e0118a45e7cbf5b7e7e11b733cb988bb90c90e8be751ac1b9562d12440aff5` | Small finite verification-only profile. |
| `analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` | `c7c40aab9e390fc46a9e48af18711dd7a61d6324006327dc822d99be343d81aa` | Selected finite RTL-entry anchor parameter profile. |
| `analysis/architecture_gate_a3_rtl_entry_qwen3_8b_v1_input_template.md` | `7cff7e53eb2b07dfc700b7a5309c3613dec725d3506cb1ad62d465e0fdc03793` | Superseded-input decision navigation. |
| `kvpress/route_a_rtl_profile.py` | `77450775b2644c59264c0c835cd610a6127315ddf521bd04323a3055b7001c70` | Pure-software profile validator and finite allocator/credit reference. |
| `tests/test_route_a_rtl_profile.py` | `2b0669362bef2a03ba4c9449e4a6ec030a46bc9947df4afcbc52d1c8a36681a8` | Directed A3 profile, capacity, ownership, credit, and generation-wrap tests. |

## Test binding

The following no-model command passed with `69 passed`:

```text
.venv/bin/python -m pytest -q \
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

This result is pure-software executable architecture-contract evidence.  It
contains no model/GPU execution, performance DSE, timing/controller model,
PPA claim, RTL correctness claim, or new A4 evidence.
