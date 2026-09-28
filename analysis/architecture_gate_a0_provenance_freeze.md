# Gate-A0 local provenance declaration — architecture-spec inputs

## Status and purpose

**Status:** `complete_local_contract_freeze; remote_report_byte_preflight_pending`.

This is a local, hash-bound declaration for the pre-RTL Route-A architecture
specification.  It freezes the identities used to author
`analysis/architecture_spec.md` and records one functional-reference semantic
that the specification relies on.  It is **not** a Gate-A pass, an RTL
authorization, a new DSE, or a replacement for the frozen A4 reports.

The local source snapshot is `/home/wz/AI/kvpress`, branch
`research/kvzap-latest`, commit
`f475adfb8e66c280de93ab4ae93f25a06a3ecff0` (2026-09-28).

## Local byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `b54a3920a7c7dc7bfd0028c2b60561e3cf2f3f70ab29553ebf0e471d37e3348d` | Gate-A0 architecture-spec draft under review. |
| `kvpress/route_a_attention.py` | `370224989113a83ff7ff9daa66076ab5957665920366dbe5d1b18bc1b319cd8e` | Functional-reference source traversal lock. |
| `analysis/route_a4112b_external_storage_lifecycle_contract.md` | `a4dc7fd4b3593478d00ac72a63a26ea44fd6c61203d2400317fd349b5e5209dd` | Exact-token lifecycle contract. |
| `analysis/route_a4120_metadata_interface_inventory_contract.md` | `fa887fd6546e70556903accdc2a15571a4e53474ce1a71b5d3d53b1223864e91` | M2 interface inventory. |
| `analysis/route_a4121_metadata_macro_envelope_contract.md` | `53924e950dcf8b0552e812146f08a6ed350b129095f9abf21a0dc143b2f11439` | M2 public-CACTI macro envelope. |
| `analysis/route_a4122_metadata_cycle_energy_contract.md` | `a1f27a3f656dbfec2d261a1f25c59b0ad8389ccd360b325616572f1738445d18` | M2 declared service/energy boundary. |
| `analysis/route_a4131_payload_organization_contract.md` | `fc58807647f10d7a8492652bb305bbc9a3614e360f41c9455b636eca454c3408` | P3 pending-HBM and staging-page mapping. |
| `analysis/route_a4133_packed_kv_hbm_realization_contract.md` | `f3ad4388dbe85976838534e946b774a3cb23117e58a975ac4a8467eb17ae9e74` | Packed-KV HBM realization boundary. |
| `analysis/route_a4134_page_source_reuse_interface_contract.md` | `6e750d68cc1490d6c43f0a38fb2d1409ebf0e4d4ab104f082491956071178d61` | Legal GQA source reuse and merge interface. |
| `analysis/route_a4135_target_payload_service_cost_contract.md` | `4136a04a237be41dda1b189d2cc3ace88354a9d82383ef52a08e05ac29c59bad` | Target payload-service accounting boundary. |
| `hardware/route_a/payload/a4135_target_profiles.json` | `53f98b5075f321328503e8a8252503151a607536db2ac16ec17dc8d0a770874d` | Declared target payload profiles. |
| `analysis/route_a4140_workload_aligned_metadata_cost_contract.md` | `a283167ac489b544debe8d07bbf482cebc3b624ad83d3eee419ccaad85b2c8ae` | Workload-aligned M2 binding. |
| `analysis/route_a4141_accounted_net_benefit_ledger_contract.md` | `ce7d66a64a127cccab3e5e2c5406b2b220635be2bf7e6ba96b1b279bd7276278` | Accounted ledger and omitted-cost budgets. |

## Accepted A4 report identities

The following values are the accepted report identities recorded by the
corresponding contracts and analyzer bindings.  They are inputs to review, not
newly produced reports.

| Evidence | Accepted report SHA-256 |
|---|---|
| A4.10 `_04` | `97f9cec11c8ffff95ce8405d303f35ddf76ea2c4078512f0d98d38e6ec0ec9e4` |
| A4.11.2b | `57da81a6fb7e3a9540fad2d0a45ba28ae418ffc69d9e81ef2fbf02090dcdc3a3` |
| A4.12.0 | `e5a7ad30b45be7acbda7c2b0b788fdfa4ee74553d6fc93bc9317dce0c4be3534` |
| A4.12.1 | `d5f0f436251cb607b884e3102788caf2e775e398542686ad9ca88b58a96e3f7d` |
| A4.12.2 | `e2578b08b852036b500ed9ce8dbba8ea9c55ec45b75a6eea02a3893473feb415` |
| A4.13.1 | `ba6ec8291d213317e953dd0ac3a050524cf10a327705c6390fe652531a98950c` |
| A4.13.3 | `fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1` |
| A4.13.4 | `2390958f801c63b7a54e725106b9e75bd36de8950b733ab9bac9d4ac2ee94597` |
| A4.13.5 | `8a3c07255d8e6382807701b437935c89207b60065df5d671dacad0b8cfb7a502` |
| A4.14.0 | `3d3cc52eade09c20ed305159d78b7bc43673db0072a4d1b9bc211bd061ae8034` |
| A4.14.1 | `0f43ec6dc30912210e4c565ebdd57554b02b7ca3f22326a498924e4cf1f2fdcb` |

## Functional-reference source-order lock

The hash-bound functional reference in `kvpress/route_a_attention.py` traverses
the three logical sources in this exact canonical order:

```text
hot -> pending -> packed
```

This locks the mathematical/finite-precision reference used by the
specification.  It does not select a physical merge pipeline, authorize source
reordering, or make a cycle-level latency claim.  Any implementation that
changes this order needs separate finite-precision validation; it cannot claim
this source binding as support.

## Preflight state

| Check | State | Interpretation |
|---|---|---|
| Local contract/source byte hashes above | verified | The listed local files were present and SHA-256 checked. |
| Ignored accepted report bytes in the local checkout | unavailable | Expected for ignored experiment outputs; their absence is a provenance gap, not a pass. |
| Remote accepted report byte hashes | pending | Two read-only SSH connection attempts to the prescribed remote endpoint closed before a command could run.  No remote command, sync, pull, test, or experiment was executed. |

The remote preflight remains: enter the prescribed `zsy:0.0` pane, run the
required `cd` and environment source command, verify branch/HEAD/status, then
SHA-256 check the exact accepted report files against this declaration.  It
must use `git pull --ff-only` only if synchronization is required; it must not
use reset, clean, or overwrite a frozen experiment.

## Consequence and next boundary

Gate-A0 closes only the local documentation/provenance refinement.  Gate A
remains open.  In particular, it still must freeze the pending-HBM delivery
realization, request-ID reuse/epoch policy, finite macro/controller assumptions,
and shared clock/dependency/arbitration/overlap contract before RTL work.

If remote byte verification is later possible, record it in a new, versioned
verification record rather than changing this local declaration or any frozen
report.  No A4.14.x variant, payload/metadata re-accounting, pruning change,
or Route-A lifecycle change is authorized by this document.
