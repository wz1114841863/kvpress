# Gate-A0 remote accepted-report verification — 2026-09-28

## Status and scope

**Status:** `passed_remote_report_byte_verification`.

This versioned record closes the remote byte-verification item that was marked
pending in `architecture_gate_a0_provenance_freeze.md`.  It verifies only the
accepted report bytes used by the pre-RTL architecture specification.  It is
not a new experiment, a rerun, a Gate-A pass, RTL authorization, or a change
to any A4 contract or frozen artifact.

## Remote preflight

The check ran in tmux pane `zsy:0.0` after:

```text
cd /home/myserver/workplace1/zsy/zsy_2/kvpress
source ../zsy_2.sh
```

The pane was found dead and was restarted before the read-only preflight.  The
remote checkout reported branch `research/kvzap-latest`, commit
`646821ad92d0ea0a11c5d2fd7b82b9640c3f4adc`, and
`research/kvzap-latest...origin/research/kvzap-latest [ahead 33]`; no changed
paths were printed by `git status --short --branch`.  No synchronization was
requested or performed: no `git pull`, reset, clean, write, test, analyzer, or
experiment command was run on the remote checkout.

## Verified report bytes

| Evidence | Remote materialized report | SHA-256 | Result |
|---|---|---|---|
| A4.10 `_04` | `analysis/experiments/route_a410_queue_staging_credit_contract_04/a410_queue_staging_credit_contract_report.json` | `97f9cec11c8ffff95ce8405d303f35ddf76ea2c4078512f0d98d38e6ec0ec9e4` | match |
| A4.11.2b | `analysis/experiments/route_a411_external_storage_lifecycle_binding_02/a4112b_external_storage_lifecycle_binding_report.json` | `57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3` | match |
| A4.12.0 | `analysis/experiments/route_a4120_metadata_interface_inventory_02/a4120_metadata_interface_inventory_report.json` | `e5a7ad30b45be7acbda7c2b0b788fdfa4ee74553d6fc93bc9317dce0c4be3534` | match |
| A4.12.1 | `analysis/experiments/route_a4121_metadata_macro_envelope_03/a4121_metadata_macro_envelope_report.json` | `d5f0f436251cb607b884e3102788caf2e775e398542686ad9ca88b58a96e3f7d` | match |
| A4.12.2 | `analysis/experiments/route_a4122_metadata_cycle_energy_02/a4122_metadata_cycle_energy_report.json` | `e2578b08b852036b500ed9ce8dbba8ea9c55ec45b75a6eea02a3893473feb415` | match |
| A4.13.1 | `analysis/experiments/route_a4131_payload_organization_envelope_01/a4131_payload_organization_envelope_report.json` | `ba6ec8291d213317e953dd0ac3a050524cf10a327705c6390fe652531a98950c` | match |
| A4.13.3 | `analysis/experiments/route_a4133_packed_kv_hbm_realization_01/a4133_packed_kv_hbm_realization_report.json` | `fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1` | match |
| A4.13.4 | `analysis/experiments/route_a4134_page_source_reuse_interface_01/a4134_page_source_reuse_interface_report.json` | `2390958f801c63b7a54e725106b9e75bd36de8950b733ab9bac9d4ac2ee94597` | match |
| A4.13.5 | `analysis/experiments/route_a4135_target_payload_service_cost_01/a4135_target_payload_service_cost_report.json` | `8a3c07255d8e6382807701b437935c89207b60065df5d671dacad0b8cfb7a502` | match |
| A4.14.0 | `analysis/experiments/route_a4140_workload_aligned_metadata_cost_01/a4140_workload_aligned_metadata_cost_report.json` | `3d3cc52eade09c20ed305159d78b7bc43673db0072a4d1b9bc211bd061ae8034` | match |
| A4.14.1 | `analysis/experiments/route_a4141_accounted_net_benefit_ledger_01/a4141_accounted_net_benefit_ledger_report.json` | `0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb` | match |

All 11 materialized report hashes equal the accepted identities in
`architecture_gate_a0_provenance_freeze.md` and
`architecture_spec.md`.

## Remaining boundary

This result makes the Gate-A0 provenance chain locally and remotely
byte-verified.  Gate A remains open: pending-HBM delivery realization,
request-ID reuse/epoch policy, finite macro/controller assumptions, and a
shared clock/dependency/arbitration/overlap contract still require review and
an executable architecture contract before any RTL work.
