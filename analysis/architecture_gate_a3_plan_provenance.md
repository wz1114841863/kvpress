# Gate-A3 plan provenance declaration

## Status

**Status:** `planned_not_started; no_rtl_authorization`.

This record binds the Gate-A3 planning revision only.  It does not freeze an
A3 manifest, deployment envelope value, implementation width, allocator policy,
macro, controller, clock, performance result, PPA result, or RTL artifact.

## Byte bindings

| Material | SHA-256 | Role |
|---|---|---|
| `analysis/architecture_spec.md` | `71594a9e2abf6929e53b2ddb2a2f4253b0d24b756e65960d548c00252185129e` | Specification revision that links the planned A3 subgate. |
| `analysis/architecture_gate_a3_plan.md` | `481893b9a56cbd8b3427a43cd93c08ed62543c7dbb25140f12f6c66e756ad096` | Planned finite RTL-boundary parameter closure. |
| `analysis/architecture_gate_a2_executable_contract.md` | `0f0a786a1a84997022c37bde683f3fa4bb79daffd24e2f9781244f049b9553fd` | A2 executable semantic baseline consumed by A3. |
| `analysis/architecture_gate_a2_provenance_freeze.md` | `787522ab13798a96e7d7190f7c8a3b6dc610624fcc4dd691e2f858ceb4d65ecf` | Historical A2 byte binding. |

## Blocking architecture-review inputs

The planned `rtl_entry_qwen3_8b_v1` cannot become an A3-complete profile until
architecture review supplies explicit deployment-envelope values, request/
session retirement ownership for `no_live_reference`, and every port-width-
changing fragment parameter.  These are intentionally not inferred from A4
workload observations.  No tests or experiments are run by this plan record.
