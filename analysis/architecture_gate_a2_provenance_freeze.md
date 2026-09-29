# Gate-A2 provenance declaration — executable transaction reference

## Status and scope

**Status:** `complete_no_model_reference_harness; pre_rtl_only`.

Gate-A2 binds a pure-software transaction reference to the current architecture
specification.  It does not bind a model trace, a GPU run, a timing model, a
physical controller, an RTL implementation, or a PPA result.  The reference is
the executable semantic baseline that a later RTL scoreboard must refine or
match.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `a58eb1eb317714ac2916ccaea8337262be97fc6026827fdf051815c058782a5c` | Specification revision naming Gate-A2 as the executable assertion reference. |
| `analysis/architecture_gate_a2_executable_contract.md` | `0f0a786a1a84997022c37bde683f3fa4bb79daffd24e2f9781244f049b9553fd` | Gate-A2 scope and assertion mapping. |
| `kvpress/route_a_architecture_reference.py` | `e9d09596e05c32949735a8f040a1b57e5c06b7a25d250faae840b340ac14ff15` | Pure-software transaction/reference harness. |
| `tests/test_route_a_architecture_reference.py` | `280d3a53f7c06cdbf43550d605821637c4720e3ce5e3db727d539657892f714e` | Directed positive and negative transaction sequences. |
| `analysis/architecture_gate_a1_pending_delivery_realization_closure.md` | `8db961ef1cd75c826d7c13c245df654bd6141152613b88beaea6f542a393f780` | Direct-pending endpoint closure consumed by the harness. |
| `analysis/architecture_gate_a1_provenance_freeze.md` | `a25744a9a50a1fc7b53c9bf1b245a4b6d1bfc3226f7b4c6518ce4c3fc82845f8` | Historical A1 specification binding. |

## Test binding

The no-model command below passed on this source snapshot with `59 passed`:

```text
.venv/bin/python -m pytest -q \
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

This establishes only executable semantic checks.  Request-ID width/epoch
policy, HBM command behavior, numeric datapath behavior, timing, ports,
controller arbitration, overlap, and all omitted-cost terms remain outside the
harness and require later Gate-A/B closure.
