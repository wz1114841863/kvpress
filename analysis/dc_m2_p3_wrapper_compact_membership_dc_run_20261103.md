# M2/P3 compact-membership paired DC run — 2026-11-03

## Authorization and scope

The user authorized a new paired DC run after the compact-membership
functional, generated-source and proxy gates passed.  This run answers only
whether the second bounded control-realization refinement changes mapped area,
sequential/combinational area, clock load, lint and timing under the unchanged
`dc_feasibility_fair_v1` contract.

It must compare against both the immutable original baseline
`dc_feasibility_fair_r5desc_20261029_r1` and the accepted first refinement
`dc_feasibility_fair_control_refinement_20261102_r1`.  It does not authorize a
clock relaxation, a larger Full-KV design, a parent-control black box, removal
of necessary state, or changes to pruning, admission, R3 publication, R6
authority or R2 arbitration.

## Frozen input

| item | value |
| --- | --- |
| constraint profile | `dc_feasibility_fair_v1` |
| clock period | 2.0 ns |
| compact functional source | `7bcd6526a941d62aabaaf59f99a31a9b5bc1c98a` |
| paired archive SHA-256 | `61d4e51cafea3c96167f371c41b31af051ca5844fd93f58ccba127b681cf7008` |
| constraint Tcl SHA-256 | `3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007` |
| target library SHA-256 | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| Full-KV / Route-A file counts | 1 / 48 |
| typed array proxies | 5/5 |

The numerical constraints, selected library, tops, source counts, proxy
boundaries and nonzero-unestimated external-service rule are identical to the
accepted first-refinement comparison.  Only the Route-A compact-membership
successor/archive identity changes.

## Run state

The static fair-v1 checker passed before launch with no unconstrained top-level
input or output.  The observed archive, proxy manifest, proxy materialization,
proxy check, constraint Tcl and library hashes match the frozen input above.

The active immutable run is:

```text
tmux:   kvzap-control-refine:p10-compact-dc
run ID: dc_feasibility_fair_m2p3_compact_20261103_r1
log:    /home/yaz80/wz_project/chisel_projects/kvpress/logs/
          m2p3_compact_p10_dc_20261103.log
root:   /home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/
          dc_feasibility_fair_m2p3_compact_20261103_r1/
```

The tmux window has `remain-on-exit on`.  At launch, proxy evidence and static
fair-v1 coverage passed, the run entered the Full-KV native `dc_shell` phase,
and no side exit, paired `RUN_PASS`, or outer marker existed yet.  This is a
healthy launch only, not a synthesis result.

Completion requires both `KVZAP_DC_FEASIBILITY_FULL_KV_EXIT=0` and
`KVZAP_DC_FEASIBILITY_ROUTE_A_EXIT=0`, paired `RUN_PASS`, outer
`KVZAP_M2P3_COMPACT_P10_DC_EXIT=0`, copied hashes, DDC/mapped HDL and native
QoR/timing/lint/fanout reports.  Do not restart or duplicate the run while it
is active; inspect it read-only after user notification.
