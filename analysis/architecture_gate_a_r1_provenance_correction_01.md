# Gate-A R1 provenance correction 01

## Scope

This versioned correction preserves
`architecture_gate_a_r1_provenance_freeze.md` as written and corrects only its
aggregated pytest count.  No source, test, accepted A4 report, A4 artifact, or
R1 contract hash is changed by this record.

## Corrected test result

The exact command printed in the R1 provenance record was re-executed on the
same R1 source/test hashes and passed with **`73 passed`**, not `76 passed`.
The earlier `76 passed` count is therefore superseded and must not be cited.

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
  tests/test_kvzap_route_a4141_accounted_net_benefit_ledger.py
```

The R1 evidence class and all stated boundaries remain unchanged: this is
pure-software protocol evidence, not model/GPU, timing, controller, PPA, or
RTL evidence.
