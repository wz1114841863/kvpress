# PM1 saved-DDC replacement readiness — 2026-11-05

## Scope

This is a read-only probe of the accepted entry_id-repair Route-A DDC.  It
checks whether the mapped production Page Manager can provide the immutable
baseline and boundary context for a controlled PM1 child-replacement screen.
It does not analyze RTL, relink, characterize, compile, mutate constraints or
write a design/netlist/DDC.

Input DDC:

```text
/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/
  dc_feasibility_fair_m2p3_entryid_repair_20261104_r1/route_a/
  route_a_control_projection.ddc
```

DDC SHA-256:
`29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326`.

## Execution closure

- tmux: `kvzap-control-refine:p17-pm1-ddc-probe`;
- output:
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/read_only/pm1_ddc_replacement_readiness_20261105_r1/`;
- retained log: `pm1_ddc_replacement_readiness_20261105_r1.log`;
- `KVZAP_PM1_SAVED_DDC_REPLACEMENT_READINESS_PASS`,
  `PROBE_READ_ONLY_COMPLETE` and outer exit zero are present;
- probe script SHA-256:
  `b4428462ebf2045fbebf85b2c0f617c6f345314a5039b472a05e2ec7e7b9e6f0`;
- summary SHA-256:
  `2ab395d21f3e59f7c5e1c90a82355eabd8b80a33a7a6823c7f35c53ccb9cf71f`.

The concurrent RD1 full DC remained live and was neither read nor modified.

## Observed replacement boundary

| property | observed value |
| --- | ---: |
| DDC designs loaded | 405 |
| Page Manager instance | `pageManager` |
| referenced design | `route_a_page_manager` |
| matching referenced designs | 1 |
| matching top instances | 1 |
| hierarchical / not flattened | true |
| boundary pins | 4,289 |
| mapped `allocatedLine` registers | 36,720 |
| mapped `reclaimLine` registers / D pins | 16 / 16 |
| selector fanin combinational cells | 135,331 |
| top clocks | 1 |
| accepted Page Manager area | 407,451.2386 |

The diagnostic `pageManager/*` direct child-pattern count is zero because that
collection form does not descend the retained reference from the current top;
it is not used by the acceptance gate.  The independently addressable design,
hierarchical instance and filtered hierarchical register/cone collections all
resolve exactly.

## Disposition

The prerequisites for a controlled bottom-up child-replacement screen pass.
DC 2018's installed command reference confirms that:

1. `change_link` can relink the unique compatible instance to a new design
   with identical port names/directions;
2. `characterize` can project the instance timing and constraint environment
   onto that subdesign;
3. only the new PM1 Page Manager subdesign then needs mapping, avoiding a new
   source compile of the crashing flat test-only baseline.

The future screen must fail closed on any port mismatch, preserve all 62,000
mapped Page Manager sequential cells expected by the accepted run, retain the
saved baseline reports, and identify bottom-up versus original top-down compile
as a remaining comparison limitation.  A complete same-fair-v1 top run remains
the final integration authority.

This probe is not mapped PM1 area/timing evidence and supports no PPA, clock
load, external-service, acceleration or hardware net-benefit conclusion.
