# Gate-A3 verification-only implementation provenance

## Status and boundary

**Status:** `verification_small_v1_complete; rtl_entry_profile_blocked_on_architecture_review_inputs`.

This record binds only the pure-software A3 verification implementation.  It
does not make `rtl_entry_qwen3_8b_v1` a complete profile, does not select
deployment values, and does not authorize Gate A or RTL.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `21e3eedafcc48c52fd4b4b0aa60608818d28b688399242dd37469805a308411f` | Specification revision recording A3's partial status. |
| `analysis/architecture_gate_a3_plan.md` | `46474e3d0925046c2f0d866929c4d0a3e8ed6ea2ca22aad748bae7d959bf820d` | A3 plan and unresolved deployment inputs. |
| `analysis/architecture_gate_a3_verification_small_v1.json` | `fafa8915f40a31530d7c2073e148ab0a09ffef6ee0cced08cf955ed0edf5a1cc` | Complete verification-only finite profile. |
| `analysis/architecture_gate_a3_rtl_entry_qwen3_8b_v1_input_template.md` | `8d713601e45bc646ce296ee3580e5e2a16fe6c70cfd9211a9940552411245e0d` | Explicit blocking deployment-input template. |
| `kvpress/route_a_rtl_profile.py` | `5b7c8fe750720e87cad4eab1664934c9772e8e1b7c6bc83f4c3f8f0209580ffa` | Profile validator, allocator safety reference, and endpoint-credit reference. |
| `tests/test_route_a_rtl_profile.py` | `fa8c00771a61e768eae3de6444a83628f9296196e6e1680c51a788356fa5262f` | Directed A3 verification tests. |

## Test binding

The following no-model command passed with `27 passed`:

```text
.venv/bin/python -m pytest -q \
  tests/test_route_a_rtl_profile.py \
  tests/test_route_a_architecture_reference.py
```

The result is a pure-software RTL-boundary parameter contract.  It contains no
model/GPU execution, A4 DSE, cycle/timing/throughput claim, PPA claim, or RTL
correctness claim.

## Required input before A3 completion

Architecture review must select the deployment envelope, response-fragment port
width, and request/session retirement owner listed in the input template.  A
new `profile_class: rtl_entry` manifest must then validate with no unresolved
architecture-review inputs.  Until then, the only accepted A3 profile is
`verification_small_v1`.
