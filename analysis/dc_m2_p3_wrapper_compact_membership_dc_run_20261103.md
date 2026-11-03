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

The new immutable run ID, tmux/log paths, static preflight result and completion
markers will be recorded here after launch.  No result is accepted from a
launch or partial phase alone; both side exits, paired `RUN_PASS`, outer exit,
copied hashes, DDC/mapped HDL and native QoR/timing/lint/fanout reports are
required.
