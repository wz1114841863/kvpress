# RTL1-I0 — cross-owner integration contract provenance freeze

## Status and evidence boundary

**Status:** `complete_rtl1_i0_contract_provenance_freeze`.

This record binds the RTL1-I0 planning artifact set at commit-time. It is
pure-software contract/provenance evidence only: no model/GPU, Chisel
behavioral integration, numerical datapath, cycle/timing/throughput, PPA, RTL
correctness, or new A4 DSE claim is made.

## Input and artifact SHA-256

| SHA-256 | Path | Role |
|---|---|---|
| `c05a75b9bc23ba44dd121cb70e12df2d8600fa17800fb4487cf705441f602a9b` | `analysis/architecture_spec.md` | Frozen architecture boundary. |
| `5d514f162b1e7926357216673d4e7ace2c3bff4f061eaedfb6d7d275769d7885` | `analysis/architecture_gate_a_r6_top_level_lifecycle_contract.md` | R6 lifecycle and retirement contract. |
| `0b4062a4009fd61aab400b3c6265e473dd0c1c3384eea2a3725c2990206ca827` | `analysis/rtl1_3_r3_r5_semantic_carrier_contract.md` | R3/R5 publication contract. |
| `af53a80028f5ea1b06f4a4eec6e8ee0cc534d5f3d77b066d449b30a5987d172c` | `analysis/rtl1_4_s2_direct_pending_semantic_carrier_contract.md` | S2/direct completion contract. |
| `c1f40fc8b59cb8173047f3e23ad36190d0e322876b2e21ccc6081e3592c3efb7` | `analysis/rtl1_5_r6_lifecycle_semantic_carrier_contract.md` | R6 authority/merge-ready contract. |
| `b725d1eacf82c5aee3081b5516d103b88706fe45098e9cc1c36a54e7d5d4fd36` | `analysis/rtl1_6_r4_packet_boundary_contract.md` | R4 packet boundary. |
| `76a5ad3ca9b5e15f400960ecf901ea12993370f69d8199458d207f57c2fadf12` | `analysis/rtl1_i_cross_owner_integration_contract.md` | I0 semantic contract. |
| `b8b84c9054a38958062b10ea4b76ef947ecdfe0ec3143d3f8044f2df45b0d4de` | `analysis/rtl1_i_composed_assertion_plan.md` | I0 composed assertion plan. |
| `af61eb63f7553b89faea4378eb403432358877b79bf104467de9fa804eb2d54b` | `analysis/rtl1_i_interface_manifest.json` | Machine-readable I0 inventory. |
| `bd35be9db7255e525d3333168cc568b818fc7a9a357cedfea9e335733bf5879f` | `kvpress/rtl1_i_integration_manifest.py` | No-model manifest validator. |
| `ecf07c25e8c19043cb9e4c2e7d520fb04e49e363d3b09805bc2d91fd74789e32` | `tools/validate_rtl1_i_integration_manifest.py` | CLI validator. |
| `b5fbcc62a7d307d3bfbc3dab8ad42e4eeb79eefc9e051192268a836717bc09db` | `tests/test_rtl1_i_integration_manifest.py` | Directed manifest tests. |

## Exact no-model preflight

```bash
.venv/bin/python tools/validate_rtl1_i_integration_manifest.py --help
.venv/bin/python tools/validate_rtl1_i_integration_manifest.py
.venv/bin/python -m pytest tests/test_rtl1_i_integration_manifest.py -q
.venv/bin/python tools/validate_rtl_entry_interface_manifest.py --require-interface-signals
.venv/bin/python tools/validate_rtl1_0_verification_binding.py
```

**Result:** PASS. The I0 validator and its `--help` command passed; pytest
reported `4 passed`; the unchanged Gate-RTL0 manifest and RTL1.0--RTL1.5
binding preflights passed.

## Frozen I0 disposition

I0 records 19 top-inert cross-owner endpoints and six required associations:
admission context; per-record publication membership/authority observation;
R2 delivery context; R4 source-instance sideband; named init/drain status; and
R5 reclaim/generation reuse. It adds no behavioral hierarchy node and leaves
all top ties unchanged. RTL1-I1 is the earliest authorized behavioral step.
