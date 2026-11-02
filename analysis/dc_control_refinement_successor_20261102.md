# Route-A control-refinement successor HDL — 2026-11-02

## Scope

This record accepts the generated-source and typed-array-proxy gates for the
first bounded Route-A control-realization refinement.  The functional RTL
source is commit `a6acd4a`; commits `961f19e`, `328ed75`, and `cc6a4b6` add
the source checker, reproducible split-HDL generator, and paired proxy
materializer.  This is not a DC mapping, timing, power, PPA, or hardware
net-benefit result.

The immutable remote raw-successor root is:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/
  control_refine_a6acd4a_p6/
```

The retained execution log is
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/control_refine_p6_hdl_20261102.log`.
CHIRRTL emission, firtool split lowering, both source checks, and the enclosing
runner completed with `KVZAP_CONTROL_REFINE_P6_HDL_EXIT=0`.

## Raw successor closure

| item | observed result |
| --- | ---: |
| split SystemVerilog files | 48 |
| aggregate SV bytes | 461,147,757 |
| ordered source-closure SHA-256 | `edb8c3a1bf3caf4a27f76e5a94f5385abd36f2e725d79300553451cc1327d5d1` |
| required typed top-port families checked | 16/16 present |
| required production control owners checked | 12/12 present and non-black-box |
| Route-A typed array interiors checked | 4/4 present and functional in the raw successor |
| old R5 functional descriptor backing tokens | 0 present |

The checked owner set includes the admission/publication ingress, M2
production control, compact metadata-admission bridge, M2/P3 parent, R5 page
manager, S2/GQA parent, lifecycle adapter, core arbiter/memory interface,
pending descriptor owner, direct-pending association materializer, and packed
activation binder.  The required external core-memory, sidecar, R5 descriptor,
three partial-source, R4 result/fault, terminal, and retire ports remain on the
top.  This proves source presence and nonempty implementation, not post-DC
observability or timing.

The generated metadata bridge contains `groupMemberMask`, `groupMappingRef`,
and `groupMappingOwner`, and contains neither `groupMembers_` state nor the old
64-member output carrier.  Thus the compact representation is present in the
actual successor rather than only in Scala source.

## Generated logical state inventory

The source checker counts a declared `reg` object only when it is the target
of a nonblocking assignment. Literal unpacked array dimensions are included.
These are generated logical state bits, not mapped sequential-cell counts or
macro area.

| category | logical state bits | state objects |
| --- | ---: | ---: |
| all emitted modules | 13,733,895 | 999,931 |
| emitted memory helper (`payload_18432x512`) | 9,437,184 | 1 |
| four named Route-A array-interior modules | 1,475,124 | 303,406 |
| retained control and other modules | 2,821,587 | 696,524 |

The memory helper is logically below an array interior; it is listed
separately so it is not mistaken for parent-control state.  Proxying the named
array body makes that helper unreachable from the synthesized top, but does
not make its physical storage or peripheral cost zero.

The largest generated state-bearing modules before proxy materialization are:

| module | logical state bits |
| --- | ---: |
| `payload_18432x512` | 9,437,184 |
| `route_a_page_manager` | 1,678,810 |
| `route_a_r5_availability_array_boundary` | 1,322,028 |
| `route_a_m2_p3_wrapper` | 990,322 |
| `route_a_m2_entry_array_boundary` | 152,498 |
| `route_a_m2_production_control_owner` | 34,801 |
| `route_a_admission_publication_ingress_adapter` | 29,625 |
| `route_a_metadata_admission_bridge` | 17,492 |

The prior raw successor has 662,504 generated logical state bits in
`route_a_metadata_admission_bridge`; the refined successor has 17,492, an
observed generated-source reduction of 645,012 bits.  The earlier DDC retained
662,404 mapped sequential cells in that hierarchy, 100 fewer than the old raw
source count.  Therefore the earlier 17,392-bit prediction is a conditional
mapped estimate; only a new same-constraint DC run can establish the mapped
successor count and area reduction.

## Paired typed-array proxy closure

The paired raw-HDL archive and proxy materialization are versioned separately:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/
  control_refine_a6acd4a_p6_paired_input.tar.gz
  control_refine_a6acd4a_p6_dc_array_proxy_manifest.json
  control_refine_a6acd4a_p6_dc_array_proxy_r1/
  control_refine_a6acd4a_p6_dc_array_proxy_check.json
```

The archive is 27,821,472 bytes and has SHA-256
`1b5ac01cd35c77c37c6d7a08843c8554ec2458eb25cc9d7d6cafbefc873ec33d`.
The paired filelists close at one Full-KV source and 48 Route-A sources.

Materialization and the independent checker both pass.  Exactly the approved
five interiors are same-header typed proxies: Full-KV S2 payload and Route-A
M2 entry, P3 stage, R5 availability/generation, and S2 payload/sidecar.  Their
named parent controls remain implemented and non-black-box.  All array,
adapter, mux/fanout, external memory, descriptor, sidecar, partial, and R4
costs remain nonzero/unestimated unless separately measured.

## Disposition

The successor HDL generation, source-level owner/port/control inspection,
logical-state inventory, and paired array-proxy materialization are **PASS**.
Together with the earlier 41/41 functional non-regression, this closes the
pre-DC gate for this bounded refinement.  It does not establish mapped-area,
fanout, lint, WNS/TNS, PPA, or net-benefit improvement.  The next evidence
step, only under its existing bounded authorization, is a same
`dc_feasibility_fair_v1` paired DC comparison using this immutable proxy root.
